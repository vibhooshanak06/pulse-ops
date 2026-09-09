"""
Metrics API service — with Redis caching.

Cache flow for every read endpoint:

  1. Check Redis cache  →  HIT  →  return cached JSON directly (no DB)
                       →  MISS →  run aggregation + DB query
                                  →  store result in Redis with TTL
                                  →  return result

  2. After aggregation writes new data, invalidate the cache keys for that
     service and project so the next request gets fresh data.

Why the cache is on the API service, not the route layer:
  The API service owns the shape of the response. Caching at the service
  layer means the cache stores the exact dict the route would serialize —
  we just json.dumps/loads it. No ORM objects or Pydantic re-validation
  needed on cache hits, which is the whole performance point.

Cache key ownership:
  CacheService owns key construction — no raw Redis key strings here.
  This keeps all key patterns documented in one place.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_service import CacheService
from app.core.redis_client import get_redis
from app.db.models.user import User
from app.repositories.metrics_repository import MetricsRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.service_repository import ServiceRepository
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

logger = logging.getLogger(__name__)

CURRENT_SNAPSHOT_MINUTES = 5


def _aggregate_windows(
    windows: list,
    window_minutes: int,
    health_status: str,
) -> CurrentMetricsSnapshot:
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

    def wavg(attr: str) -> float:
        return round(
            sum(getattr(w, attr) * w.request_count for w in windows) / total_requests, 2
        )

    return CurrentMetricsSnapshot(
        avg_latency_ms  = wavg("avg_latency_ms"),
        p50_latency_ms  = wavg("p50_latency_ms"),
        p95_latency_ms  = round(max(w.p95_latency_ms for w in windows), 2),
        p99_latency_ms  = round(max(w.p99_latency_ms for w in windows), 2),
        error_rate      = round(total_errors / total_requests, 6),
        request_count   = total_requests,
        throughput_rpm  = round(total_requests / max(window_minutes, 1), 2),
        health_status   = health_status,
        window_minutes  = window_minutes,
    )


class MetricsApiService:

    def __init__(self, db: AsyncSession, cache: CacheService | None = None) -> None:
        self._db           = db
        self._cache        = cache        # None → caching disabled (tests / no Redis)
        self._orgs         = OrganizationRepository(db)
        self._projects     = ProjectRepository(db)
        self._services     = ServiceRepository(db)
        self._metrics_repo = MetricsRepository(db)
        self._aggregator   = MetricAggregationService(db, cache)

    # ── Ownership helpers ─────────────────────────────────────────────────────

    async def _require_org_access(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        if not await self._orgs.get_by_id_for_user(org_id, user_id):
            raise HTTPException(status_code=404, detail="Organization not found.")

    async def _require_project_access(
        self, org_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        await self._require_org_access(org_id, user_id)
        if not await self._projects.get_by_id(project_id, org_id):
            raise HTTPException(status_code=404, detail="Project not found.")

    async def _resolve_service(self, project_id: uuid.UUID, service_id: uuid.UUID):
        svc = await self._services.get_by_id(service_id, project_id)
        if svc is None:
            raise HTTPException(status_code=404, detail="Service not found.")
        return svc

    # ── Service metrics ───────────────────────────────────────────────────────

    async def get_service_metrics(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        service_id: uuid.UUID,
        user: User,
        window_minutes: int = 60,
    ) -> ServiceMetricsResponse:

        await self._require_project_access(org_id, project_id, user.id)
        service = await self._resolve_service(project_id, service_id)

        svc_id_str = str(service_id)

        # ── Cache check ───────────────────────────────────────────────────────
        if self._cache:
            cached = await self._cache.get_service_metrics(svc_id_str, window_minutes)
            if cached is not None:
                logger.debug("Cache HIT — service_metrics:%s:%d", svc_id_str[:8], window_minutes)
                return ServiceMetricsResponse(**cached)
            logger.debug("Cache MISS — service_metrics:%s:%d", svc_id_str[:8], window_minutes)

        # ── Compute ───────────────────────────────────────────────────────────
        await self._aggregator.aggregate_service(service.id, window_minutes)
        await self._aggregator.aggregate_endpoints(service.id, window_minutes)

        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        aggregates = await self._metrics_repo.get_aggregates_for_service(
            service_id=service.id, since=since
        )
        time_series = [MetricWindow.model_validate(a) for a in aggregates]

        snapshot_since = datetime.now(timezone.utc) - timedelta(minutes=CURRENT_SNAPSHOT_MINUTES)
        recent  = [a for a in aggregates if a.window_start >= snapshot_since]
        service = await self._resolve_service(project_id, service_id)
        current = _aggregate_windows(recent, CURRENT_SNAPSHOT_MINUTES, service.health_status)

        endpoints = await self._build_endpoint_rows(service.id, since)

        response = ServiceMetricsResponse(
            service_id    = service.id,
            service_name  = service.name,
            health_status = service.health_status,
            current       = current,
            time_series   = time_series,
            endpoints     = endpoints,
        )

        # ── Cache store ───────────────────────────────────────────────────────
        if self._cache:
            await self._cache.set_service_metrics(
                svc_id_str, window_minutes,
                response.model_dump(mode="json"),
            )

        return response

    # ── Service health snapshot ───────────────────────────────────────────────

    async def get_service_health(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        service_id: uuid.UUID,
        user: User,
    ) -> ServiceHealthResponse:

        await self._require_project_access(org_id, project_id, user.id)
        service = await self._resolve_service(project_id, service_id)

        svc_id_str = str(service_id)

        # ── Try Redis health snapshot first ───────────────────────────────────
        if self._cache:
            snapshot = await self._cache.get_health_snapshot(svc_id_str)
            if snapshot is not None:
                logger.debug("Health snapshot HIT — service:%s", svc_id_str[:8])
                return ServiceHealthResponse(**snapshot)
            logger.debug("Health snapshot MISS — service:%s", svc_id_str[:8])

        # ── Fall back to DB aggregates ────────────────────────────────────────
        since   = datetime.now(timezone.utc) - timedelta(minutes=CURRENT_SNAPSHOT_MINUTES)
        windows = await self._metrics_repo.get_aggregates_for_service(
            service_id=service.id, since=since
        )
        current = _aggregate_windows(windows, CURRENT_SNAPSHOT_MINUTES, service.health_status)

        response = ServiceHealthResponse(
            service_id    = service.id,
            service_name  = service.name,
            health_status = service.health_status,
            current       = current,
        )

        # Write back to Redis so next request is a cache hit
        if self._cache:
            await self._cache.set_health_snapshot(
                svc_id_str,
                response.model_dump(mode="json"),
            )

        return response

    # ── Project overview ──────────────────────────────────────────────────────

    async def get_overview(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        user: User,
        window_minutes: int = 60,
    ) -> OverviewResponse:

        await self._require_project_access(org_id, project_id, user.id)

        proj_id_str = str(project_id)

        # ── Cache check ───────────────────────────────────────────────────────
        if self._cache:
            cached = await self._cache.get_metrics_overview(proj_id_str, window_minutes)
            if cached is not None:
                logger.debug("Cache HIT — overview:%s:%d", proj_id_str[:8], window_minutes)
                return OverviewResponse(**cached)
            logger.debug("Cache MISS — overview:%s:%d", proj_id_str[:8], window_minutes)

        # ── Compute ───────────────────────────────────────────────────────────
        await self._aggregator.aggregate_all_services_in_project(
            project_id=project_id,
            window_minutes=window_minutes,
        )

        services = await self._services.list_for_project(project_id)

        health_counts: dict[str, int] = {
            "healthy": 0, "degraded": 0, "critical": 0, "unknown": 0
        }
        service_summaries: list[ServiceSummary] = []
        since = datetime.now(timezone.utc) - timedelta(minutes=CURRENT_SNAPSHOT_MINUTES)

        for svc in services:
            wins = await self._metrics_repo.get_aggregates_for_service(
                service_id=svc.id, since=since
            )
            snap = _aggregate_windows(wins, CURRENT_SNAPSHOT_MINUTES, svc.health_status)
            h    = svc.health_status if svc.health_status in health_counts else "unknown"
            health_counts[h] += 1
            service_summaries.append(ServiceSummary(
                service_id     = svc.id,
                service_name   = svc.name,
                health_status  = svc.health_status,
                p95_latency_ms = snap.p95_latency_ms,
                error_rate     = snap.error_rate,
                request_count  = snap.request_count,
                last_seen_at   = svc.last_seen_at,
            ))

        project_aggregates = await self._metrics_repo.get_aggregates_for_all_services(
            project_id=project_id,
            since=datetime.now(timezone.utc) - timedelta(minutes=window_minutes),
        )
        window_map: dict[datetime, list] = {}
        for agg in project_aggregates:
            window_map.setdefault(agg.window_start, []).append(agg)

        project_series: list[MetricWindow] = []
        for ws_key in sorted(window_map):
            ws        = window_map[ws_key]
            total_req = sum(w.request_count for w in ws)
            total_err = sum(w.error_count   for w in ws)
            if total_req == 0:
                continue

            def wagg(attr: str, _ws=ws, _tr=total_req) -> float:
                return round(
                    sum(getattr(w, attr) * w.request_count for w in _ws) / _tr, 2
                )

            project_series.append(MetricWindow(
                window_start   = ws_key,
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

        response = OverviewResponse(
            total_services    = len(services),
            healthy_services  = health_counts["healthy"],
            degraded_services = health_counts["degraded"],
            critical_services = health_counts["critical"],
            unknown_services  = health_counts["unknown"],
            active_incidents  = 0,
            services          = service_summaries,
            time_series       = project_series,
        )

        # ── Cache store ───────────────────────────────────────────────────────
        if self._cache:
            await self._cache.set_metrics_overview(
                proj_id_str, window_minutes,
                response.model_dump(mode="json"),
            )

        return response

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _build_endpoint_rows(
        self,
        service_id: uuid.UUID,
        since: datetime,
    ) -> list[EndpointMetricRow]:
        from app.db.models.endpoint import Endpoint
        from sqlalchemy import select

        result = await self._db.execute(
            select(Endpoint).where(Endpoint.service_id == service_id)
        )
        endpoints = list(result.scalars().all())

        rows: list[EndpointMetricRow] = []
        for ep in endpoints:
            wins = await self._metrics_repo.get_aggregates_for_service(
                service_id=service_id, since=since, endpoint_id=ep.id
            )
            if not wins:
                continue
            total_req = sum(w.request_count for w in wins)
            total_err = sum(w.error_count   for w in wins)
            if total_req == 0:
                continue
            rows.append(EndpointMetricRow(
                endpoint_id    = ep.id,
                path           = ep.path,
                method         = ep.method,
                request_count  = total_req,
                avg_latency_ms = round(
                    sum(w.avg_latency_ms * w.request_count for w in wins) / total_req, 2
                ),
                p95_latency_ms = round(max(w.p95_latency_ms for w in wins), 2),
                error_rate     = round(total_err / total_req, 6),
                throughput_rpm = round(
                    total_req / max(
                        (wins[-1].window_end - wins[0].window_start).total_seconds() / 60, 1
                    ), 2
                ),
            ))

        return sorted(rows, key=lambda r: r.request_count, reverse=True)
