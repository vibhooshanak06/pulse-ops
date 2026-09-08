"""
AiExplanation model.

The structured output of the AI incident intelligence engine.

This model stores exactly what the LLM returned, parsed into typed fields.
The raw LLM response is also preserved for debugging and model comparison.

Key constraint: the AI may ONLY reason over evidence in IncidentEvidence.
If the evidence is thin, the `limitations` field must say so explicitly.

Field structure mirrors the expected LLM response format:

  summary           → 2-3 sentence human-readable incident description
  probable_causes   → JSONB array, each item:
                        { description, confidence (0-1), supporting_evidence[] }
  confidence        → overall confidence score 0.0–1.0
  recommended_actions → JSONB array of investigation step strings
  limitations       → explicit statement of what the AI could NOT determine
  model_used        → which LLM model was called (for audit + reproducibility)
  prompt_tokens     → token usage for cost monitoring
  completion_tokens → token usage for cost monitoring

The UNIQUE constraint on incident_id enforces that only one AI explanation
is generated per incident. To regenerate, the existing row must be deleted
first — this is an intentional friction to prevent runaway API costs.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AiExplanation(Base):
    __tablename__ = "ai_explanations"

    __table_args__ = (
        # One AI explanation per incident — enforced at DB level
        UniqueConstraint("incident_id", name="uq_ai_explanation_incident"),
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

    # ── Structured AI output ──────────────────────────────────────────────────
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        # e.g. "The payment service experienced significant degradation starting
        # at 14:31 UTC. P95 latency increased 796% from baseline and error rate
        # reached 16.4%. The latency spike preceded the error rate increase by
        # approximately 60 seconds."
    )
    probable_causes: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        # Array of cause objects, each with:
        # {
        #   "description": "Backend or downstream dependency degradation...",
        #   "confidence": 0.76,
        #   "supporting_evidence": [
        #     "P95 latency increased from 240ms to 2140ms",
        #     "Latency anomaly preceded error rate increase"
        #   ]
        # }
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        # Overall confidence 0.0–1.0.
        # Low confidence must be reflected in the limitations field.
    )
    recommended_actions: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        # Array of investigation step strings, e.g.:
        # [
        #   "Check downstream service health for payment processor",
        #   "Review database slow query logs starting at 14:30 UTC",
        #   "Inspect infrastructure metrics for the payment service pods"
        # ]
    )
    limitations: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        # REQUIRED field — must never be empty.
        # e.g. "Root cause cannot be determined from API metrics alone.
        # Database metrics, infrastructure logs, and deployment history
        # were not available at the time of this analysis."
    )

    # ── Raw LLM output ────────────────────────────────────────────────────────
    raw_response: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        # The unmodified LLM response string before parsing.
        # Preserved for debugging, model comparison, and prompt tuning.
    )

    # ── Model metadata ────────────────────────────────────────────────────────
    model_used: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
        # e.g. "gpt-4o-mini", "gpt-4o"
        # Stored so we know which model generated each explanation.
    )
    prompt_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        # LLM API usage — useful for cost tracking and prompt optimization.
    )
    completion_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    incident: Mapped["Incident"] = relationship("Incident", back_populates="ai_explanation")

    def __repr__(self) -> str:
        return (
            f"<AiExplanation id={self.id} "
            f"incident={self.incident_id} "
            f"confidence={self.confidence:.2f} "
            f"model={self.model_used}>"
        )
