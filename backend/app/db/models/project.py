"""
Project model.

Projects sit directly under an Organization and act as logical
groupings of services. A typical setup:

  Acme Corp (organization)
  ├── Production (project)   ← services: payment-api, order-api, user-api
  └── Staging    (project)   ← services: payment-api-staging

Why projects exist as a separate layer:
- An organization may run multiple independent products.
- Each project gets its own API keys, so telemetry from "Production"
  is never mixed with "Staging" data.
- Access control can be scoped per project in V2.

Relationships:
  Organization → Project (many-to-one)
  Project → Service       (one-to-many)
  Project → ApiKey        (one-to-many)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Parent organization ───────────────────────────────────────────────────
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,         # fast lookup: "all projects for org X"
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        # Unique within an org, but two orgs can have a project named "production"
        # The uniqueness constraint is (organization_id, slug) — see below
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    # ── Table-level constraints ────────────────────────────────────────────────
    from sqlalchemy import UniqueConstraint
    __table_args__ = (
        # slug must be unique within an organization
        UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="projects",
    )
    services: Mapped[list["Service"]] = relationship(
        "Service",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} slug={self.slug}>"
