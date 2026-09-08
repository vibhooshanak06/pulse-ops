"""
ApiKey model.

API keys are the authentication mechanism for telemetry ingestion.
They are separate from user JWT tokens for a critical reason:

  User JWT   → identifies a human, expires in 60 minutes, used by the dashboard
  API Key    → identifies a project's SDK integration, long-lived, used by services

Security design:
  - We store only the SHA-256 hash of the key, never the plain-text value.
  - The plain-text key is shown ONCE at creation time (like GitHub PATs).
  - The `key_prefix` (first 8 chars, e.g. "po_live_") is stored in plain text
    so users can identify which key is which in the dashboard without
    exposing the full secret.
  - On each telemetry request, we hash the incoming key and compare to
    the stored hash — constant-time comparison prevents timing attacks.

Key format:  po_live_<random_32_chars>
             └──────┘ └──────────────┘
             prefix    random portion (SHA-256 hashed for storage)

Relationships:
  Project → ApiKey (many-to-one)
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

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

    # ── Key storage ───────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        # Human-readable label so you can tell keys apart:
        # "Payment Service Production", "Order API Staging"
    )
    key_prefix: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        # Stored in plain text — safe to display in the dashboard.
        # Example: "po_live_ab"
    )
    key_hash: Mapped[str] = mapped_column(
        String(64),     # SHA-256 hex digest is always 64 chars
        nullable=False,
        unique=True,    # two different projects cannot accidentally have the same key
        index=True,     # fast lookup by hash on every telemetry request
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,     # most lookups filter on is_active=True
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # Updated on each successful telemetry ingestion.
        # Useful for identifying stale or unused keys.
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        # Set when the key is revoked. We keep the row (soft delete)
        # so audit logs show when and why it was revoked.
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    project: Mapped["Project"] = relationship("Project", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id} prefix={self.key_prefix} active={self.is_active}>"
