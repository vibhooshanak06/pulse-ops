"""
Endpoint model.

An Endpoint is a specific (path, method) combination within a Service.
Examples:
  POST /api/payment/process
  GET  /api/orders/{order_id}
  GET  /api/products

Why track endpoints separately from services?
  Service-level metrics tell you the service is degraded.
  Endpoint-level metrics tell you *which* endpoint is causing it.
  This is the difference between "payment-api is slow" and
  "POST /api/payment/process is slow, but GET /api/payment/status is fine."

Auto-creation:
  Endpoints are created automatically by the telemetry ingestion pipeline
  the first time a (service_id, path, method) combination is seen.
  Engineers never need to register endpoints manually.

Path normalization:
  The SDK normalizes paths using the matched route pattern:
    /api/orders/123   →  /api/orders/{order_id}
  This prevents high-cardinality metrics (one row per unique ID).

Relationships:
  Service → Endpoint (many-to-one)
  Endpoint → TelemetryEvent (one-to-many, optional)
  Endpoint → MetricAggregate (one-to-many, optional)
  Endpoint → Anomaly (one-to-many, optional)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Endpoint(Base):
    __tablename__ = "endpoints"

    __table_args__ = (
        # Each (service, path, method) combination must be unique.
        # This is the natural key — we never want duplicate endpoint rows.
        UniqueConstraint("service_id", "path", "method", name="uq_endpoint_service_path_method"),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Parent service ────────────────────────────────────────────────────────
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,         # fast lookup: "all endpoints for service X"
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        # Normalized route pattern: /api/orders/{order_id}
        # Max 1000 chars to handle deeply nested paths
    )
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        # HTTP method: GET, POST, PUT, PATCH, DELETE
        # Always stored uppercase
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # Updated whenever a telemetry event arrives for this endpoint.
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    service: Mapped["Service"] = relationship("Service", back_populates="endpoints")

    telemetry_events: Mapped[list["TelemetryEvent"]] = relationship(
        "TelemetryEvent",
        back_populates="endpoint",
        # No cascade delete — we keep telemetry even if endpoint record changes
    )
    metric_aggregates: Mapped[list["MetricAggregate"]] = relationship(
        "MetricAggregate",
        back_populates="endpoint",
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(
        "Anomaly",
        back_populates="endpoint",
    )

    def __repr__(self) -> str:
        return f"<Endpoint id={self.id} {self.method} {self.path}>"
