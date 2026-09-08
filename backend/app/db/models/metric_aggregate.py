"""
MetricAggregate model.

Pre-calculated metric summaries over fixed time windows.

Why pre-aggregate instead of computing on-demand from telemetry_events?

  On-demand approach:
    SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
    FROM telemetry_events
    WHERE service_id = ? AND timestamp BETWEEN ? AND ?

  At 3.6M rows/hour, this query scans hundreds of thousands of rows
  per dashboard request. With 10 concurrent users refreshing every
  30 seconds, the database never has a quiet moment.

  Pre-aggregate approach:
    SELECT p95_latency_ms FROM metric_aggregates
    WHERE service_id = ? AND window_start >= ?
    ORDER BY window_start

  This scans at most ~60 rows for a 1-hour view. Three orders of
  magnitude fewer rows touched per query.

Time window strategy:
  The metrics engine (Phase 7) writes 1-minute aggregates continuously.
  Dashboard queries roll up 1-minute aggregates for the requested window.
  This gives us:
    - 1-minute resolution for last-hour views
    - 5-minute resolution for last-day views (roll up 5 × 1-min rows)
    - Configurable in V2 via window_size_minutes column

Percentile calculation:
  P50, P95, P99 are computed using numpy.percentile() over the raw
  latency values in each 1-minute window. The results are stored here.
  We cannot recompute exact percentiles from aggregates — this is a
  known tradeoff (we'd need T-Digest for that, V2 concern).

Composite indexes:
  (service_id, window_start DESC) — dashboard queries for a service over time
  (endpoint_id, window_start DESC) — endpoint detail queries
  Both use DESC because dashboards always ask for the most recent data first.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MetricAggregate(Base):
    __tablename__ = "metric_aggregates"

    __table_args__ = (
        Index(
            "ix_metric_service_window",
            "service_id",
            "window_start",
            postgresql_ops={"window_start": "DESC"},
        ),
        Index(
            "ix_metric_endpoint_window",
            "endpoint_id",
            "window_start",
            postgresql_ops={"window_start": "DESC"},
        ),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Foreign keys ──────────────────────────────────────────────────────────
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )
    endpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("endpoints.id", ondelete="SET NULL"),
        nullable=True,
        # NULL means this aggregate is service-level (not endpoint-specific).
        # Non-NULL means it covers one specific endpoint.
    )

    # ── Time window ───────────────────────────────────────────────────────────
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Inclusive start of the aggregation window.
        # For 1-minute windows: 14:32:00, 14:33:00, 14:34:00 ...
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Exclusive end of the window (window_start + 1 minute).
    )
    window_size_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        # Stored explicitly so different window sizes can coexist.
        # V2: add 5-minute and 1-hour aggregates for longer time ranges.
    )

    # ── Volume metrics ────────────────────────────────────────────────────────
    request_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        # Total requests in this window.
    )
    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        # Requests with status_code >= 400.
    )
    error_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        # error_count / request_count. Range: 0.0 to 1.0.
        # 0.154 means 15.4% error rate.
    )
    throughput_rpm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        # Requests per minute. For 1-min windows: same as request_count.
        # For 5-min windows: request_count / 5.
    )

    # ── Latency metrics (all in milliseconds) ─────────────────────────────────
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    min_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p50_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        # Median latency. 50% of requests were faster than this.
    )
    p95_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        # 95th percentile. The "slow but not worst" experience.
        # This is the primary anomaly detection signal for latency.
    )
    p99_latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        # 99th percentile. Worst 1% of requests.
        # Critical for SLA monitoring and payment flow health.
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    service: Mapped["Service"] = relationship("Service", back_populates="metric_aggregates")
    endpoint: Mapped["Endpoint | None"] = relationship("Endpoint", back_populates="metric_aggregates")

    def __repr__(self) -> str:
        return (
            f"<MetricAggregate service={self.service_id} "
            f"window={self.window_start} "
            f"p95={self.p95_latency_ms:.1f}ms "
            f"err={self.error_rate:.1%}>"
        )
