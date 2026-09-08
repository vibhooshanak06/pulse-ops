"""
Anomaly model.

An anomaly is a single detected deviation from the baseline in one metric
for one service (and optionally one endpoint) at one point in time.

Examples:
  - P95 latency for payment-service spiked from 240ms to 2140ms
  - Error rate for order-service jumped from 0.8% to 16.4%
  - Request volume for user-service dropped 80% (traffic anomaly)

One anomaly ≠ one incident.
Multiple related anomalies are correlated into an incident (Phase 10).
The `incident_id` FK is NULL until the correlator assigns it.

Anomaly score design:
  statistical_score  → z-score normalized to 0.0–1.0
  ml_score           → Isolation Forest decision normalized to 0.0–1.0
  combined_score     → weighted combination of the two signals
  severity           → bucketed from combined_score:
                         0.0–0.3  → LOW
                         0.3–0.6  → MEDIUM
                         0.6–0.8  → HIGH
                         0.8–1.0  → CRITICAL

Why keep both scores?
  In an interview: "I keep both so I can show which signal fired —
  a purely statistical anomaly vs one that Isolation Forest also flagged
  indicates higher confidence. I also use this to tune thresholds
  independently per signal without reprocessing historical data."

metric_type values:
  latency       → P95 or P99 latency exceeded baseline
  error_rate    → error_rate exceeded baseline
  throughput    → request volume changed abnormally
  request_count → raw request count anomaly (traffic spike/drop)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    __table_args__ = (
        # Most common query pattern: "all open anomalies for service X, recent first"
        Index(
            "ix_anomaly_service_detected",
            "service_id",
            "detected_at",
            postgresql_ops={"detected_at": "DESC"},
        ),
        # Correlator query: "all unassigned anomalies in last N minutes"
        Index(
            "ix_anomaly_incident_detected",
            "incident_id",
            "detected_at",
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
        # NULL: service-wide anomaly
        # Non-NULL: isolated to a specific endpoint
    )
    metric_aggregate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metric_aggregates.id", ondelete="SET NULL"),
        nullable=True,
        # The specific aggregate window that triggered this anomaly.
        # Preserved for audit; SET NULL if aggregate is cleaned up.
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        # NULL until the correlator assigns this anomaly to an incident.
        # SET NULL if the incident is deleted (anomaly record preserved).
    )

    # ── What was detected ─────────────────────────────────────────────────────
    metric_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        # "latency" | "error_rate" | "throughput" | "request_count"
    )
    baseline_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        # The expected "normal" value from the historical baseline window.
    )
    current_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        # The observed value that triggered the anomaly.
    )
    deviation_percent: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        # ((current - baseline) / baseline) * 100
        # Positive: above baseline. Negative: below baseline (traffic drops).
    )

    # ── Detection scores ──────────────────────────────────────────────────────
    statistical_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        # Z-score based signal normalized to 0.0–1.0
    )
    ml_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        # Isolation Forest signal normalized to 0.0–1.0
    )
    combined_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        index=True,     # ORDER BY combined_score DESC for severity ranking
        # Weighted combination: 0.4 * statistical + 0.6 * ml
    )

    # ── Severity ──────────────────────────────────────────────────────────────
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="LOW",
        index=True,
        # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        # Set by the detection engine at detection time, not server receipt.
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # Set when the metric returns to within normal range.
        # NULL means the anomaly is still active.
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    service: Mapped["Service"] = relationship("Service", back_populates="anomalies")
    endpoint: Mapped["Endpoint | None"] = relationship("Endpoint", back_populates="anomalies")
    incident: Mapped["Incident | None"] = relationship("Incident", back_populates="anomalies")

    def __repr__(self) -> str:
        return (
            f"<Anomaly id={self.id} "
            f"type={self.metric_type} "
            f"severity={self.severity} "
            f"score={self.combined_score:.2f}>"
        )
