"""
Service model.

A Service represents one running application that has the PulseOps
SDK installed. Examples: "payment-api", "order-service", "user-service".

The `health_status` column is a denormalized snapshot — it stores the
current computed health so dashboard list queries can return service health
without recalculating from metrics every time. Redis also caches this
(Phase 8), but the DB column is the durable fallback.

Why denormalize health_status here?
  The alternative is to compute health on every GET /services query by
  joining to metric_aggregates. At scale that becomes expensive.
  Writing health_status directly here (updated by the metrics engine)
  makes the list query a simple SELECT with no joins.

health_status values:
  healthy   → all metrics within normal range
  degraded  → one or more metrics above warning threshold
  critical  → one or more metrics above critical threshold
  unknown   → no recent telemetry (< MIN_DATA_POINTS in last window)

Relationships:
  Project → Service (many-to-one)
  Service → Endpoint (one-to-many)
  Service → TelemetryEvent (one-to-many)
  Service → MetricAggregate (one-to-many)
  Service → Anomaly (one-to-many)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Service(Base):
    __tablename__ = "services"

    __table_args__ = (
        # Service name must be unique within a project
        UniqueConstraint("project_id", "name", name="uq_service_project_name"),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Parent project ────────────────────────────────────────────────────────
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        # Matches the service_name sent by the SDK in telemetry payloads.
        # The ingestion API uses this to resolve/create the Service record.
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Denormalized health snapshot ──────────────────────────────────────────
    health_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
        index=True,     # dashboard can filter: WHERE health_status = 'critical'
        # Values: "healthy", "degraded", "critical", "unknown"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # Updated whenever a telemetry event arrives for this service.
        # Used to detect services that have gone silent.
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    project: Mapped["Project"] = relationship("Project", back_populates="services")

    endpoints: Mapped[list["Endpoint"]] = relationship(
        "Endpoint",
        back_populates="service",
        cascade="all, delete-orphan",
    )
    telemetry_events: Mapped[list["TelemetryEvent"]] = relationship(
        "TelemetryEvent",
        back_populates="service",
        cascade="all, delete-orphan",
    )
    metric_aggregates: Mapped[list["MetricAggregate"]] = relationship(
        "MetricAggregate",
        back_populates="service",
        cascade="all, delete-orphan",
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(
        "Anomaly",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Service id={self.id} name={self.name} health={self.health_status}>"
