"""
TelemetryEvent model.

One row per API request captured by the PulseOps SDK.
This is the raw, immutable event log — the source of truth for
everything the metrics engine, anomaly detector, and AI layer produce.

Volume characteristics:
  A service handling 100 req/s generates 360,000 rows/hour.
  At 10 services that's 3.6M rows/hour.
  Design decisions that account for this:

  1. Composite index on (service_id, timestamp DESC)
     The metrics engine always queries: "events for service X between T1 and T2"
     This index makes that a fast index scan, not a full table scan.

  2. Composite index on (endpoint_id, timestamp DESC)
     Endpoint-level metrics use the same pattern.

  3. Integer status_code, not a string
     Saves ~4 bytes per row. At 3.6M rows/hour, that's ~14MB/hour saved
     just on this one column. Multiplied across millions of rows it matters.

  4. FLOAT latency_ms, not NUMERIC
     Telemetry latency doesn't need bank-precision decimals.
     FLOAT is 8 bytes, NUMERIC(10,2) is variable — FLOAT wins on speed.

  5. No CASCADE delete from endpoint
     If an endpoint record is ever cleaned up, we keep the raw telemetry
     for historical analysis. endpoint_id becomes nullable (SET NULL).

V2 note:
  This table is the primary candidate for TimescaleDB hypertables.
  The (service_id, timestamp) partitioning maps perfectly to TS chunks.
  The migration is a DROP TABLE + CREATE TABLE AS hypertable — planned.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    # ── Composite indexes ─────────────────────────────────────────────────────
    # Defined at table level so we can specify DESC ordering on timestamp,
    # which matches the ORDER BY in time-window queries.
    __table_args__ = (
        Index(
            "ix_telemetry_service_timestamp",
            "service_id",
            "timestamp",
            postgresql_ops={"timestamp": "DESC"},
        ),
        Index(
            "ix_telemetry_endpoint_timestamp",
            "endpoint_id",
            "timestamp",
            postgresql_ops={"timestamp": "DESC"},
        ),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
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
        # Nullable: set NULL if the endpoint record is removed,
        # preserving the raw telemetry row for historical queries.
    )

    # ── Telemetry payload ─────────────────────────────────────────────────────
    endpoint_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        # Denormalized copy of the path string.
        # Avoids a join to endpoints table on high-frequency queries.
        # Tradeoff: slight storage increase, significant read performance gain.
    )
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        # HTTP method, always uppercase: GET, POST, PUT, PATCH, DELETE
    )
    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,     # filter: WHERE status_code >= 500 (error queries)
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        # Time from request start to response completion, milliseconds.
        # Captured by the SDK using time.perf_counter() — monotonic clock.
    )

    # ── Derived flags ─────────────────────────────────────────────────────────
    is_error: Mapped[bool] = mapped_column(
        # True when status_code >= 400.
        # Denormalized for fast error-rate aggregation:
        #   SELECT COUNT(*) FILTER (WHERE is_error) / COUNT(*) ...
        # is faster than:
        #   SELECT COUNT(*) FILTER (WHERE status_code >= 400) / COUNT(*) ...
        # because is_error can be indexed while status_code >= 400 cannot.
        nullable=False,
        default=False,
        index=True,
    )

    # ── Timestamp ─────────────────────────────────────────────────────────────
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Set by the SDK at capture time (client clock).
        # We use the client timestamp, not server receipt time, because
        # we want to align telemetry with what the user experienced.
        # server_default is NOT used here — timestamp comes from the payload.
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        # Server receipt time. Useful for detecting clock skew between
        # the SDK client and the server.
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    service: Mapped["Service"] = relationship("Service", back_populates="telemetry_events")
    endpoint: Mapped["Endpoint | None"] = relationship("Endpoint", back_populates="telemetry_events")

    def __repr__(self) -> str:
        return (
            f"<TelemetryEvent id={self.id} "
            f"{self.method} {self.endpoint_path} "
            f"→ {self.status_code} {self.latency_ms:.1f}ms>"
        )
