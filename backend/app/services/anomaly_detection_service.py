"""
Anomaly Detection Service — orchestrates the full detection pipeline.

FULL PIPELINE per service per detection cycle:

  1. Load the last N metric_aggregate windows (baseline + current)
  2. Split into baseline window (older) and current window (latest)
  3. Compute baseline statistics from the historical window
  4. If no baseline → skip (service too new, not enough data)
  5. Run statistical detectors (latency, error_rate, throughput)
  6. Run Isolation Forest on the same windows
  7. Compute combined score
  8. If anomalous:
       a. Check deduplication (skip if same metric_type already active)
       b. Write Anomaly row to DB
  9. If no longer anomalous for a previously active anomaly → resolve it

BASELINE vs CURRENT SPLIT:
  We use the last (BASELINE_WINDOWS + 1) aggregate rows.
  The most recent row is "current"; everything before it is "baseline".

  Example with BASELINE_WINDOWS = 30:
    windows[0..28]  → baseline (30 rows)
    windows[29]     → current  (1 row, the window we're evaluating)

  This means the detector always has BASELINE_WINDOWS data points for
  statistical computation and evaluates exactly one window at a time.

DETECTION INTERVAL:
  This service is called:
    - On-demand: triggered from the anomaly API route when the dashboard
      requests fresh anomaly data
    - By the ml-engine scheduler every minute (Phase 9 runner)

  The on-demand trigger ensures the first dashboard load always shows
  up-to-date anomaly state.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.anomaly_repository import AnomalyRepository
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.service_repository import ServiceRepository
from app.services.anomaly_detection.baseline import compute_baseline
from app.services.anomaly_detection.isolation_forest import detect_with_isolation_forest
from app.services.anomaly_detection.scorer import compute_combined_score
from app.services.anomaly_detection.statistical import (
    detect_error_rate_anomaly,
    detect_latency_anomaly,
    detect_throughput_anomaly,
)

logger = logging.getLogger(__name__)

# How many historical 1-minute windows to use as the baseline
BASELINE_WINDOWS = 30

# Total windows to load: baseline + 1 current
TOTAL_WINDOWS = BASELINE_WINDOWS + 1

# Z-score threshold — values this many std devs from mean are anomalous
ZSCORE_THRESHOLD = 3.0

# Isolation Forest contamination rate
IF_CONTAMINATION = 0.05


class AnomalyDetectionService:
    """
    Orchestrates the full anomaly detection pipeline for one service.

    Usage:
        svc = AnomalyDetectionService(db)
        results = await svc.detect_for_service(service_id)
        # results is a list of created Anomaly ORM objects (may be empty)
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db        = db
        self._metrics   = MetricsRepository(db)
        self._anomalies = AnomalyRepository(db)
        self._services  = ServiceRepository(db)

    async def detect_for_service(
        self,
        service_id: uuid.UUID,
    ) -> list:
        """
        Run one detection cycle for a service.
        Returns a list of newly created Anomaly ORM objects.
        Returns empty list if no anomalies detected or insufficient data.
        """
        since = datetime.now(timezone.utc) - timedelta(minutes=TOTAL_WINDOWS + 5)

        # Load recent service-level aggregate windows
        windows = await self._metrics.get_aggregates_for_service(
            service_id=service_id,
            since=since,
        )

        if len(windows) < TOTAL_WINDOWS:
            logger.debug(
                "Skipping detection for service %s — only %d windows "
                "(need %d)",
                str(service_id)[:8], len(windows), TOTAL_WINDOWS,
            )
            return []

        # Split: baseline = all but last, current = last window
        baseline_windows = windows[:-1]
        current_window   = windows[-1]

        # ── 1. Compute baseline ───────────────────────────────────────────────
        baseline = compute_baseline(baseline_windows)
        if not baseline.has_baseline:
            logger.debug(
                "No baseline for service %s — skipping", str(service_id)[:8]
            )
            return []

        # ── 2. Statistical detection ──────────────────────────────────────────
        stat_results = []

        if baseline.p95_latency:
            stat_results.append(detect_latency_anomaly(
                baseline  = baseline.p95_latency,
                current_p95 = current_window.p95_latency_ms,
                threshold   = ZSCORE_THRESHOLD,
            ))

        if baseline.error_rate:
            stat_results.append(detect_error_rate_anomaly(
                baseline            = baseline.error_rate,
                current_error_rate  = current_window.error_rate,
                threshold           = ZSCORE_THRESHOLD,
            ))

        if baseline.throughput_rpm:
            stat_results.append(detect_throughput_anomaly(
                baseline            = baseline.throughput_rpm,
                current_throughput  = current_window.throughput_rpm,
                threshold           = ZSCORE_THRESHOLD,
            ))

        # ── 3. Isolation Forest detection ─────────────────────────────────────
        if_result = detect_with_isolation_forest(
            baseline_windows = baseline_windows,
            current_window   = current_window,
            contamination    = IF_CONTAMINATION,
        )

        # ── 4. Combined score ─────────────────────────────────────────────────
        combined = compute_combined_score(stat_results, if_result)

        logger.debug(
            "Service %s window %s: combined=%.3f severity=%s triggered=%s",
            str(service_id)[:8],
            current_window.window_start.isoformat(),
            combined.combined_score,
            combined.severity,
            combined.triggered_metrics,
        )

        # ── 5. Write anomalies + resolve recovered metrics ────────────────────
        created_anomalies = []

        if combined.is_anomalous:
            # One anomaly row per triggered metric type (deduplication applied)
            metrics_to_write = combined.triggered_metrics or ["multi_metric"]

            for metric_type in metrics_to_write:
                # Deduplication: skip if an unresolved anomaly already exists
                if await self._anomalies.has_active_anomaly(service_id, metric_type):
                    logger.debug(
                        "Dedup skip: active anomaly already exists for "
                        "service=%s metric=%s",
                        str(service_id)[:8], metric_type,
                    )
                    continue

                # Find the matching statistical result for per-metric values
                stat = next(
                    (s for s in stat_results if s.metric_type == metric_type), None
                )

                anomaly = await self._anomalies.create(
                    service_id          = service_id,
                    endpoint_id         = None,
                    metric_aggregate_id = current_window.id,
                    metric_type         = metric_type,
                    baseline_value      = stat.baseline_value if stat else combined.baseline_value,
                    current_value       = stat.current_value  if stat else combined.current_value,
                    deviation_percent   = stat.deviation_percent if stat else combined.deviation_percent,
                    statistical_score   = combined.statistical_score,
                    ml_score            = combined.ml_score,
                    combined_score      = combined.combined_score,
                    severity            = combined.severity,
                    detected_at         = current_window.window_start,
                )
                created_anomalies.append(anomaly)
                logger.info(
                    "Anomaly created: service=%s metric=%s severity=%s "
                    "score=%.3f baseline=%.2f current=%.2f",
                    str(service_id)[:8], metric_type, combined.severity,
                    combined.combined_score, anomaly.baseline_value,
                    anomaly.current_value,
                )

        else:
            # Metric returned to normal — resolve any active anomalies
            for metric_type in ["latency", "error_rate", "throughput"]:
                resolved = await self._anomalies.resolve(service_id, metric_type)
                if resolved:
                    logger.info(
                        "Resolved %d anomaly(s) for service=%s metric=%s",
                        resolved, str(service_id)[:8], metric_type,
                    )

        return created_anomalies

    async def detect_for_project(
        self,
        project_id: uuid.UUID,
    ) -> list:
        """
        Run detection for all services in a project.
        Called by the scheduler and by the anomaly overview API.
        Returns a flat list of all created anomalies.
        """
        services = await self._services.list_for_project(project_id)
        all_anomalies = []
        for service in services:
            anomalies = await self.detect_for_service(service.id)
            all_anomalies.extend(anomalies)
        return all_anomalies
