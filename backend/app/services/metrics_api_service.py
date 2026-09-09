"""
Metrics API service.

Read layer for the dashboard API. Responsibilities:
  1. Enforce org/project ownership (same pattern as other services)
  2. Trigger on-demand aggregation for any windows not yet computed
  3. Shape metric_aggregate rows into response schemas

On-demand aggregation strategy:
  When a dashboard request arrives, we check if there are newer telemetry
  events than the last computed aggregate. If yes, we run aggregation for
  the missing windows before returning data. This means:
    - The first request after new traffic always shows fresh data
    - No separate cron job is required for V1 (though Phase 9 adds one)
    - Aggregation adds ~20-50ms to the first request; subsequent requests
      within the same minute hit the already-computed aggregates

Current snapshot calculation:
  We don't use a single most-recent 1-min window because it might be
  incomplete (we're mid-minute) or have very few events (just started).
  Instead we roll up all aggregates from the last N minutes — this gives
  a stable, representative "current" view.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.endpoint_repository import EndpointRepository
from app.schemas.metrics import (
    CurrentMetricsSnapshot,
    EndpointMetricRow,
    MetricWindow,
    OverviewResponse,
    ServiceHealthResponse,
    ServiceMetricsResponse,
    ServiceSummary,
)
from app.services.metrics_aggregation_service import MetricAggregationService


# Rolling window used for "current" snapshot display
CURRENT_SNAPSHOT_MINUTES = 5


def _aggregate_windows(
    windows: list,
    window_minutes: int,
    health_status: str,
) -> CurrentMetricsSnapshot:
    """
    Roll up a list of MetricAggregate rows into one CurrentMetricsSnapshot.
    Uses weighted averages for latency (weighted by request_count) and
    sums for counts — this produces correct aggregated values, not
    an average of averages.
    """
    if not windows:
        return CurrentMetricsSnapshot(
            avg_latency_ms=0.0, p50_latency_ms=0.0,
            p95_latency_ms=0.0, p99_latency_ms=0.0,
            error_rate=0.0, request_count=0,
            throughput_rpm=0.0, health_status=health_status,
            window_minutes=window_minutes,
        )

    total_requests = sum(w.request_count for w in windows)
    total_errors   = sum(w.error_count   for w in windows)

    if total_requests == 0:
        return CurrentMetricsSnapshot(
            avg_latency_ms=0.0, p50_latency_ms=0.0,
            p95_latency_ms=0.0, p99_latency_ms=0.0,
            error_rate=0.0, request_count=0,
            throughput_rpm=0.0, health_status=health_status,
            window_minutes=window_minutes,
        )

    # Weighted average latencies
    def weighted_avg(attr: str) -> float:
        total = sum(getattr(w, attr) * w.request_count for w in windows)
        return round(total / total_requests, 2)

    # P95/P99: take the max across windows as a conservative estimate.
    # True cross-window percentiles require raw data; max is the safe
    # approximation that never understates performance issues.
    p95 = round(max(w.p95_latency_ms for w in windows), 2)
    p99 = round(max(w.p99_latency_ms for w in windows), 2)
    p50 = weighted_avg("p50_latency_ms")

    return CurrentMetricsSnapshot(
        avg_latency_ms  = weighted_avg("avg_latency_ms"),
        p50_latency_ms  = p50,
        p95_latency_ms  = p95,
        p99_latency_ms  = p99,
        error_rate      = round(total_errors / total_requests, 6),
        request_count   = total_requests,
        throughput_rpm  = round(total_requests / max(window_minutes, 1), 2),
        health_status   = health_status,
        window_minutes  = window_minutes,
    )


class MetricsApiService:
    def __init__(self, db: AsyncSession) -> None:
        self._db          = db
        self._orgs        = OrganizationRepository(db)
        self._projects    = ProjectRepository(db)
        self._services    = ServiceRepository(db)
        self._endpoints   = EndpointRepository(db)
        self._metrics_repo = MetricsRepository(db)
        self._aggregator   = MetricAggregationService(db)

    # ── Ownership helpers ─────────────────────────────────────────────────────

    async def _require_org_access(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        if not await self._orgs.get_by_id_for_user(org_id, user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Organization not found.")

    async def _require_project_access(
        self, org_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        await self._require_org_access(org_id, user_id)
        if not await self._projects.get_by_id(project_id, org_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Project not found.")

    async def _resolve_service(
        self, project_id: uuid.UUID, service_id: uuid.UUID
    ):
        svc = await self._services.get_by_id(service_id, project_id)
        if svc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Service not found.")
        return svc

    # ── Public API methods ────────────────────────────────────────────────────

    async def get_service_metrics(
        self,
        org_id:      uuid.UUID,
        project_id:  uuid.UUID,
        service_id:  uuid.UUID,
        user:        User,
        window_minutes: int = 60,
    ) -> ServiceMetricsResponse:
        """
        Full metrics for one service — used by the service detail page.
        Triggers aggregation for any un-aggregated windows before responding.
        """
        await self._require_project_access(org_id, project_id, user.id)
        service = await self._resolve_service(project_id, service_id)

        # Run on-demand aggregation to fill any missing windows
        await self._aggregator.aggregate_service(
            service_id=service.id,
            window_minutes=window_minutes,
        )
        await self._aggregator.aggregate_endpoints(
            service_id=service.id,
            window_minutes=window_minutes,
        )

        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

        # Fetch service-level time series
        aggregates = await self._metrics_repo.get_aggregates_for_service(
            service_id=service.id,
            since=since,
        )
        time_series = [MetricWindow.model_validate(a) for a in aggregates]

        # Current snapshot from last CURRENT_SNAPSHOT_MINUTES
        snapshot_since = datetime.now(timezone.utc) - timedelta(minutes=CURRENT_SNAPSHOT_MINUTES)
        recent = [a for a in aggregates if a.window_start >= snapshot_since]
        current = _aggregate_windows(recent, CURRENT_SNAPSHOT_MINUTES, service.health_status)

        # Per-endpoint summary
        endpoints = await self._build_endpoint_rows(service.id, since)

        # Refresh service object to get updated health_status
        service = await self._resolve_service(project_id, service_id)

        return ServiceMetricsResponse(
            service_id    = service.id,
            service_name  = service.name,
            health_status = service.health_status,
            current       = current,
            time_series   = time_series,
            endpoints     = endpoints,
        )

    async def get_service_health(
        self,
        org_id:     uuid.UUID,
        project_id: uuid.UUID,
        service_id: uuid.UUID,
        user:       User,
    ) -> ServiceHealthResponse:
        """
        Lightweight health snapshot — service list and sidebar.
        Uses cached aggregates, does not trigger re-aggregation.
        """
        await self._require_project_access(org_id, project_id, user.id)
        service = await self._resolve_service(project_id, service_id)

        since   = datetime.now(timezone.utc) - timedelta(minutes=CURRENT_SNAPSHOT_MINUTES)
        windows = await self._metrics_repo.get_aggregates_for_service(
            service_id=service.id, since=since
        )
        current = _aggregate_windows(windows, CURRENT_SNAPSHOT_MINUTES, service.health_status)

        return ServiceHealthResponse(
            service_id    = service.id,
            service_name  = service.name,
            health_status = service.health_status,
            current       = current,
        )

    async def get_overview(
        self,
        org_id:     uuid.UUID,
        project_id: uuid.UUID,
        user:       User,
        window_minutes: int = 60,
    ) -> OverviewResponse:
        """
        Overview dashboard — aggregated view across all project services.
        Triggers aggregation for all services before responding.
        """
        await self._require_project_access(org_id, project_id, user.id)

        # Aggregate all services in the project
        await self._aggregator.aggregate_all_services_in_project(
            project_id=project_id,
            window_minutes=window_minutes,
        )

        services = await self._services.list_for_project(project_id)

        # Count services by health status
        health_counts: dict[str, int] = {
            "healthy": 0, "degraded": 0, "critical": 0, "unknown": 0
        }
        service_summaries: list[ServiceSummary] = []

        since = datetime.now(timezone.utc) - timedelta(minutes=CURRENT_SNAPSHOT_MINUTES)

        for svc in services:
            windows = await self._metrics_repo.get_aggregates_for_service(
                service_id=svc.id, since=since
            )
            snapshot = _aggregate_windows(windows, CURRENT_SNAPSHOT_MINUTES, svc.health_status)
            h = svc.health_status if svc.health_status in health_counts else "unknown"
            health_counts[h] += 1

            service_summaries.append(ServiceSummary(
                service_id     = svc.id,
                service_name   = svc.name,
                health_status  = svc.health_status,
                p95_latency_ms = snapshot.p95_latency_ms,
                error_rate     = snapshot.error_rate,
                request_count  = snapshot.request_count,
                last_seen_at   = svc.last_seen_at,
            ))

        # Project-level time series: sum of all service aggregates per window
        project_aggregates = await self._metrics_repo.get_aggregates_for_all_services(
            project_id=project_id,
            since=datetime.now(timezone.utc) - timedelta(minutes=window_minutes),
        )
        # Group by window_start and sum across services
        window_map: dict[datetime, list] = {}
        for agg in project_aggregates:
            window_map.setdefault(agg.window_start, []).append(agg)

        project_series: list[MetricWindow] = []
        for window_start in sorted(window_map):
            ws = window_map[window_start]
            total_req = sum(w.request_count for w in ws)
            total_err = sum(w.error_count   for w in ws)
            if total_req == 0:
                continue

            def wagg(attr: str) -> float:
                return round(
                    sum(getattr(w, attr) * w.request_count for w in ws) / total_req, 2
                )

            project_series.append(MetricWindow(
                window_start   = window_start,
                window_end     = ws[0].window_end,
                request_count  = total_req,
                error_count    = total_err,
                error_rate     = round(total_err / total_req, 6),
                throughput_rpm = round(sum(w.throughput_rpm for w in ws), 2),
                avg_latency_ms = wagg("avg_latency_ms"),
                min_latency_ms = round(min(w.min_latency_ms for w in ws), 2),
                max_latency_ms = round(max(w.max_latency_ms for w in ws), 2),
                p50_latency_ms = wagg("p50_latency_ms"),
                p95_latency_ms = round(max(w.p95_latency_ms for w in ws), 2),
                p99_latency_ms = round(max(w.p99_latency_ms for w in ws), 2),
            ))

        return OverviewResponse(
            total_services    = len(services),
            healthy_services  = health_counts["healthy"],
            degraded_services = health_counts["degraded"],
            critical_services = health_counts["critical"],
            unknown_services  = health_counts["unknown"],
            active_incidents  = 0,   # Phase 11 will populate this
            services          = service_summaries,
            time_series       = project_series,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _build_endpoint_rows(
        self,
        service_id: uuid.UUID,
        since: datetime,
    ) -> list[EndpointMetricRow]:
        """Build per-endpoint summary rows for the endpoint table."""
        from app.db.models.endpoint import Endpoint
        from sqlalchemy import select

        # Get all endpoints for this service
        result = await self._db.execute(
            select(Endpoint).where(Endpoint.service_id == service_id)
        )
        endpoints = list(result.scalars().all())

        rows: list[EndpointMetricRow] = []
        for ep in endpoints:
            windows = await self._metrics_repo.get_aggregates_for_service(
                service_id=service_id,
                since=since,
                endpoint_id=ep.id,
            )
            if not windows:
                continue

            total_req = sum(w.request_count for w in windows)
            total_err = sum(w.error_count   for w in windows)
            if total_req == 0:
                continue

            rows.append(EndpointMetricRow(
                endpoint_id    = ep.id,
                path           = ep.path,
                method         = ep.method,
                request_count  = total_req,
                avg_latency_ms = round(
                    sum(w.avg_latency_ms * w.request_count for w in windows) / total_req, 2
                ),
                p95_latency_ms = round(max(w.p95_latency_ms for w in windows), 2),
                error_rate     = round(total_err / total_req, 6),
                throughput_rpm = round(total_req / max(
                    (windows[-1].window_end - windows[0].window_start).total_seconds() / 60, 1
                ), 2),
            ))

        return sorted(rows, key=lambda r: r.request_count, reverse=True)
