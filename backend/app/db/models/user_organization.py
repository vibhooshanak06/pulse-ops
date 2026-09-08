"""
UserOrganization model — many-to-many join table.

A user can belong to multiple organizations (e.g. a contractor working
across clients). An organization has many users.

The `role` column supports basic RBAC:
  - owner:  full access, can delete the organization
  - admin:  can manage projects, services, API keys
  - member: read access + telemetry ingestion

The composite unique constraint on (user_id, organization_id) prevents
a user being added to the same org twice.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserOrganization(Base):
    __tablename__ = "user_organizations"

    __table_args__ = (
        # Prevent duplicate memberships
        UniqueConstraint("user_id", "organization_id", name="uq_user_org"),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Foreign keys ──────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Role ──────────────────────────────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="member",
        # Valid values: "owner", "admin", "member"
        # Enforced in the service layer; a CHECK constraint is added in V2
        # when roles stabilize.
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="organization_memberships")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="memberships")

    def __repr__(self) -> str:
        return f"<UserOrganization user={self.user_id} org={self.organization_id} role={self.role}>"
