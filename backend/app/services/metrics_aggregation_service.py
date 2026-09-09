"""
Metric aggregation service.

Converts raw telemetry_events into pre-calculated metric_aggregates.

Design decisions explained:

WHY NUMPY FOR PERCENTILES:
  PostgreSQL has percentile_cont() but it requires pulling all rows into
  Python anyway via SQLAlchemy. Since we already have the latency values
  in memory as a Python list, numpy.percentile() is the cleanest path.
  At V2 scale we'd use TimescaleDB continuous aggregates.

WHY 1-MINUTE WINDOWS:
  1-minute granularity lets us show "last 60 minutes" with 60 data points
  on a chart — enough detail without excessive storage.
  The dashboard rolls these up into 5-min or 1-hour views by averaging
  multiple 1-min windows together (done in MetricsApiService).

HEALTH STATUS THRESHOLDS:
  These are intentionally conservative defaults.
  - CRITICAL: error_rate > 5% OR p95 > 2000ms
  - DEGRADED:  error_rate > 1% OR p95 > 500ms
  - HEALTHY:   everything below thresholds
  - UNKNOWN:   no data in last window

  In V2 these become configurable per-project thresholds.

TRIGGER:
  This service is called:
  1. On-demand: when GET /metrics or GET /services/{id}/metrics is called
     and there are events newer than the last aggregate.
  2. By the scheduled runner in ml-engine (Phase 9) every minute.

  Calling it on-demand means the first dashboard load after new traffic
  always shows fresh metrics without waiting for a cron job.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.service import Service
from app.db.models.telemetry_event import TelemetryEvent
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.service_repository import ServiceRepository


# ── Health thresholds ─────────────────────────────────────────────────────────

ERROR_RATE_DEGRADED  = 0.01   # 1%
ERROR_RATE_CRITICAL  = 0.05   # 5%
P95_DEGRADED_MS      = 500.0
P95_CRITICAL_MS      = 2000.0


@dataclass
class WindowMetrics:
    """Calculated metrics for one time window."""
    request_count:    int
    error_count:      int
    error_rate:       float
    throughput_rpm:   float
    avg_latency_ms:   float
    min_latency_ms:   float
    max_latency_ms:   float
    p50_latency_ms:   float
    p95_latency_ms:   float
    p99_latency_ms:   float


def _calculate_metrics(
    events: list[TelemetryEvent],
    window_size_minutes: int = 1,
) -> WindowMetrics:
    """
    Pure calculation function — no DB access, easy to unit test.

    Takes a list of TelemetryEvent objects and returns all 10 metrics.
    Called once per service-level window and once per endpoint-level window.
    """
    request_count = len(events)

    if request_count == 0:
        return WindowMetrics(
            request_count=0, error_count=0, error_rate=0.0,
            throughput_rpm=0.0, avg_latency_ms=0.0,
            min_latency_ms=0.0, max_latency_ms=0.0,
            p50_latency_ms=0.0, p95_latency_ms=0.0, p99_latency_ms=0.0,
        )

    latencies    = np.array([e.latency_ms for e in events], dtype=np.float64)
    error_count  = sum(1 for e in events if e.is_error)
    error_rate   = error_count / request_count
    throughput   = request_count / window_size_minutes   # requests per minute

    return WindowMetrics(
        request_count  = request_count,
        error_count    = error_count,
        error_rate     = round(error_rate, 6),
        throughput_rpm = round(float(throughput), 2),
        avg_latency_ms = round(float(np.mean(latencies)), 2),
        min_latency_ms = round(float(np.min(latencies)), 2),
        max_latency_ms = round(float(np.max(latencies)), 2),
        p50_latency_ms = round(float(np.percentile(latencies, 50)), 2),
        p95_latency_ms = round(float(np.percentile(latencies, 95)), 2),
        p99_latency_ms = round(float(np.percentile(latencies, 99)), 2),
    )


def _determine_health_status(metrics: WindowMetrics) -> str:
    """
    Map calculated metrics to a health status string.
    Called after each window aggregation to update service.health_status.
    """
    if metrics.request_count == 0:
        return "unknown"
    if (metrics.error_rate >= ERROR_RATE_CRITICAL or
            metrics.p95_latency_ms >= P95_CRITICAL_MS):
        return "critical"
    if (metrics.error_rate >= ERROR_RATE_DEGRADED or
            metrics.p95_latency_ms >= P95_DEGRADED_MS):
        return "degraded"
    return "healthy"


class MetricAggregationService:
    """
    Aggregates raw telemetry events into metric_aggregates rows.

    Usage:
        svc = MetricAggregationService(db)
        await svc.aggregate_service(service_id, window_minutes=60)
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db       = db
        self._metrics  = MetricsRepository(db)
        self._services = ServiceRepository(db)

    async def aggregate_service(
        self,
        service_id: uuid.UUID,
        window_minutes: int = 60,
        window_size_minutes: int = 1,
    ) -> list[dict]:
        """
        Aggregate all telemetry for a service over the last `window_minutes`
        into `window_size_minutes`-sized buckets.

        Returns a list of window result dicts (used by the API layer to
        build the response without another DB round-trip).

        Example: window_minutes=60, window_size_minutes=1
          → creates up to 60 aggregate rows, one per minute
        """
        now        = datetime.now(timezone.utc)
        range_start = now - timedelta(minutes=window_minutes)

        # Quantise to clean minute boundaries
        # e.g. 14:32:47 → 14:32:00
        range_start = range_start.replace(second=0, microsecond=0)

        results = []
        cursor  = range_start

        while cursor < now:
            window_end = cursor + timedelta(minutes=window_size_minutes)

            events = await self._metrics.get_events_in_window(
                service_id=service_id,
                window_start=cursor,
                window_end=window_end,
            )

            if events:
                m = _calculate_metrics(events, window_size_minutes)
                await self._metrics.upsert_aggregate(
                    service_id          = service_id,
                    endpoint_id         = None,   # service-level aggregate
                    window_start        = cursor,
                    window_end          = window_end,
                    window_size_minutes = window_size_minutes,
                    request_count       = m.request_count,
                    error_count         = m.error_count,
                    error_rate          = m.error_rate,
                    throughput_rpm      = m.throughput_rpm,
                    avg_latency_ms      = m.avg_latency_ms,
                    min_latency_ms      = m.min_latency_ms,
                    max_latency_ms      = m.max_latency_ms,
                    p50_latency_ms      = m.p50_latency_ms,
                    p95_latency_ms      = m.p95_latency_ms,
                    p99_latency_ms      = m.p99_latency_ms,
                )
                results.append({
                    "window_start": cursor.isoformat(),
                    "window_end":   window_end.isoformat(),
                    **m.__dict__,
                })

            cursor = window_end

        # Update service health status from the most recent window
        if results:
            last_m = results[-1]
            health = _determine_health_status(
                WindowMetrics(**{k: last_m[k] for k in WindowMetrics.__dataclass_fields__})
            )
            await self._services.update_health_and_last_seen(service_id, health)

        return results

    async def aggregate_endpoints(
        self,
        service_id: uuid.UUID,
        window_minutes: int = 60,
        window_size_minutes: int = 1,
    ) -> None:
        """
        Aggregate per-endpoint metrics for all endpoints of a service.
        Called after aggregate_service() so service-level is always up-to-date first.
        """
        now         = datetime.now(timezone.utc)
        range_start = (now - timedelta(minutes=window_minutes)).replace(second=0, microsecond=0)

        endpoint_ids = await self._metrics.get_distinct_endpoints_for_service(service_id)

        for endpoint_id in endpoint_ids:
            cursor = range_start
            while cursor < now:
                window_end = cursor + timedelta(minutes=window_size_minutes)

                events = await self._metrics.get_events_in_window(
                    service_id   = service_id,
                    window_start = cursor,
                    window_end   = window_end,
                    endpoint_id  = endpoint_id,
                )

                if events:
                    m = _calculate_metrics(events, window_size_minutes)
                    await self._metrics.upsert_aggregate(
                        service_id          = service_id,
                        endpoint_id         = endpoint_id,
                        window_start        = cursor,
                        window_end          = window_end,
                        window_size_minutes = window_size_minutes,
                        request_count       = m.request_count,
                        error_count         = m.error_count,
                        error_rate          = m.error_rate,
                        throughput_rpm      = m.throughput_rpm,
                        avg_latency_ms      = m.avg_latency_ms,
                        min_latency_ms      = m.min_latency_ms,
                        max_latency_ms      = m.max_latency_ms,
                        p50_latency_ms      = m.p50_latency_ms,
                        p95_latency_ms      = m.p95_latency_ms,
                        p99_latency_ms      = m.p99_latency_ms,
                    )

                cursor = window_end

    async def aggregate_all_services_in_project(
        self,
        project_id: uuid.UUID,
        window_minutes: int = 60,
    ) -> None:
        """
        Aggregate all services in a project — called by the scheduler.
        Also triggers endpoint-level aggregation for each service.
        """
        services = await self._services.list_for_project(project_id)
        for service in services:
            await self.aggregate_service(service.id, window_minutes)
            await self.aggregate_endpoints(service.id, window_minutes)
