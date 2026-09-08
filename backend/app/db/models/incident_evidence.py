"""
IncidentEvidence model.

Structured evidence collected about an incident BEFORE the AI is invoked.

This is the most architecturally important model in the intelligence layer.

Why collect evidence separately?
  The AI receives only what is in this table — nothing else.
  This enforces the evidence-grounded constraint:
    - The LLM cannot access the database directly.
    - The LLM cannot invent metrics it wasn't given.
    - Every claim the AI makes can be traced to a specific row here.

  If this evidence record contains only 2 data points, the AI must say
  "insufficient evidence to determine root cause" — not invent one.

What's stored:
  baseline_metrics    → the "normal" values before the incident window
  current_metrics     → the values observed during the incident window
  metric_changes      → calculated deltas and percent changes
  anomaly_timeline    → ordered list of anomaly detections with timestamps
  affected_services   → service names involved
  affected_endpoints  → endpoint paths involved

All fields use JSONB so the evidence schema can evolve without migrations.
The structure is validated in the evidence collector (Phase 12) before storage.

The UNIQUE constraint on incident_id enforces the one-to-one relationship
at the database level — not just in application code.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"

    __table_args__ = (
        # Enforce one evidence record per incident at DB level
        UniqueConstraint("incident_id", name="uq_evidence_incident"),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Parent incident ───────────────────────────────────────────────────────
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Baseline snapshot ─────────────────────────────────────────────────────
    baseline_metrics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        # Example:
        # {
        #   "avg_latency_ms": 145.2,
        #   "p95_latency_ms": 238.7,
        #   "p99_latency_ms": 412.1,
        #   "error_rate": 0.008,
        #   "throughput_rpm": 342.0
        # }
    )

    # ── Current snapshot ──────────────────────────────────────────────────────
    current_metrics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        # Same keys as baseline_metrics, values from the incident window.
    )

    # ── Computed changes ──────────────────────────────────────────────────────
    metric_changes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        # Example:
        # {
        #   "p95_latency_ms": {
        #     "baseline": 238.7,
        #     "current": 2140.3,
        #     "change_percent": 796.5,
        #     "direction": "increase"
        #   },
        #   "error_rate": {
        #     "baseline": 0.008,
        #     "current": 0.164,
        #     "change_percent": 1950.0,
        #     "direction": "increase"
        #   }
        # }
    )

    # ── Anomaly timeline ──────────────────────────────────────────────────────
    anomaly_timeline: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        # Ordered list of anomaly events, e.g.:
        # [
        #   {"timestamp": "...", "metric_type": "latency",
        #    "severity": "HIGH", "value": 2140, "baseline": 238},
        #   {"timestamp": "...", "metric_type": "error_rate",
        #    "severity": "CRITICAL", "value": 0.164, "baseline": 0.008}
        # ]
        # The ordering matters: latency before errors → suggests upstream cause
    )

    # ── Affected scope ────────────────────────────────────────────────────────
    affected_services: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        # List of service name strings
    )
    affected_endpoints: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        # List of endpoint path strings
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    baseline_window_minutes: Mapped[int | None] = mapped_column(
        nullable=True,
        # How many minutes of history were used to calculate the baseline.
        # Stored so the AI prompt can mention it for transparency.
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    incident: Mapped["Incident"] = relationship("Incident", back_populates="evidence")

    def __repr__(self) -> str:
        return f"<IncidentEvidence id={self.id} incident={self.incident_id}>"
