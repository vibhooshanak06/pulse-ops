"""
Metrics repository.

Two responsibilities:
  1. Read raw telemetry_events for aggregation (used by MetricAggregationService)
  2. Read metric_aggregates for dashboard API responses (used by MetricsApiService)

Percentile calculation note:
  PostgreSQL has percentile_cont() but it requires a GROUP BY for each
  service/endpoint which gets verbose. We fetch latency values into Python
  and use numpy.percentile() — cleaner code, same result, acceptable
  for the data volumes we handle in V1 (< 50k events per window).

  At scale (V2) we'd use TimescaleDB continuous aggregates or a streaming
  rollup to pre-calculate percentiles without pulling raw values.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.metric_aggregate import MetricAggregate
from app.db.models.telemetry_event import TelemetryEvent


class MetricsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Raw event reads (for aggregation) ─────────────────────────────────────

    async def get_events_in_window(
        self,
        service_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
        endpoint_id: uuid.UUID | None = None,
    ) -> list[TelemetryEvent]:
        """
        Fetch all raw events in a time window for one service.
        Optionally filtered to a single endpoint.
        Used by the aggregation engine to calculate per-window metrics.
        """
        conditions = [
            TelemetryEvent.service_id == service_id,
            TelemetryEvent.timestamp >= window_start,
            TelemetryEvent.timestamp < window_end,
        ]
        if endpoint_id is not None:
            conditions.append(TelemetryEvent.endpoint_id == endpoint_id)

        result = await self._db.execute(
            select(TelemetryEvent)
            .where(and_(*conditions))
            .order_by(TelemetryEvent.timestamp)
        )
        return list(result.scalars().all())

    async def get_distinct_endpoints_for_service(
        self, service_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Returns all endpoint IDs that have at least one telemetry event."""
        result = await self._db.execute(
            select(TelemetryEvent.endpoint_id)
            .where(
                TelemetryEvent.service_id == service_id,
                TelemetryEvent.endpoint_id.is_not(None),
            )
            .distinct()
        )
        return [row[0] for row in result.all()]

    # ── Aggregate writes ───────────────────────────────────────────────────────

    async def upsert_aggregate(
        self,
        service_id: uuid.UUID,
        endpoint_id: uuid.UUID | None,
        window_start: datetime,
        window_end: datetime,
        window_size_minutes: int,
        request_count: int,
        error_count: int,
        error_rate: float,
        throughput_rpm: float,
        avg_latency_ms: float,
        min_latency_ms: float,
        max_latency_ms: float,
        p50_latency_ms: float,
        p95_latency_ms: float,
        p99_latency_ms: float,
    ) -> MetricAggregate:
        """
        Insert a new metric aggregate row.
        We insert fresh rows rather than updating existing ones — this preserves
        the full history. The window_start + service_id combination naturally
        forms a logical unique key without an explicit constraint.
        """
        aggregate = MetricAggregate(
            service_id=service_id,
            endpoint_id=endpoint_id,
            window_start=window_start,
            window_end=window_end,
            window_size_minutes=window_size_minutes,
            request_count=request_count,
            error_count=error_count,
            error_rate=error_rate,
            throughput_rpm=throughput_rpm,
            avg_latency_ms=avg_latency_ms,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            p50_latency_ms=p50_latency_ms,
            p95_latency_ms=p95_latency_ms,
            p99_latency_ms=p99_latency_ms,
        )
        self._db.add(aggregate)
        await self._db.flush()
        return aggregate

    # ── Aggregate reads (for dashboard API) ───────────────────────────────────

    async def get_aggregates_for_service(
        self,
        service_id: uuid.UUID,
        since: datetime,
        window_size_minutes: int = 1,
        endpoint_id: uuid.UUID | None = None,
    ) -> list[MetricAggregate]:
        """
        Fetch metric aggregates for a service over a time range.
        Used by the dashboard to render charts.
        Ordered oldest-first so chart libraries get chronological data.
        """
        conditions = [
            MetricAggregate.service_id == service_id,
            MetricAggregate.window_start >= since,
            MetricAggregate.window_size_minutes == window_size_minutes,
        ]
        if endpoint_id is not None:
            conditions.append(MetricAggregate.endpoint_id == endpoint_id)
        else:
            # Service-level aggregates have NULL endpoint_id
            conditions.append(MetricAggregate.endpoint_id.is_(None))

        result = await self._db.execute(
            select(MetricAggregate)
            .where(and_(*conditions))
            .order_by(MetricAggregate.window_start)
        )
        return list(result.scalars().all())

    async def get_latest_aggregate_for_service(
        self,
        service_id: uuid.UUID,
    ) -> MetricAggregate | None:
        """Most recent service-level aggregate — used for health snapshot."""
        result = await self._db.execute(
            select(MetricAggregate)
            .where(
                MetricAggregate.service_id == service_id,
                MetricAggregate.endpoint_id.is_(None),
            )
            .order_by(MetricAggregate.window_start.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_aggregates_for_all_services(
        self,
        project_id: uuid.UUID,
        since: datetime,
    ) -> list[MetricAggregate]:
        """
        Fetch latest service-level aggregates across all services in a project.
        Used by GET /metrics/overview.
        Joins through services table to enforce project scoping.
        """
        from app.db.models.service import Service

        result = await self._db.execute(
            select(MetricAggregate)
            .join(Service, Service.id == MetricAggregate.service_id)
            .where(
                Service.project_id == project_id,
                MetricAggregate.window_start >= since,
                MetricAggregate.endpoint_id.is_(None),
            )
            .order_by(MetricAggregate.window_start.desc())
        )
        return list(result.scalars().all())
