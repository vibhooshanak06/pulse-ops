"""
Organization repository.

Multi-tenancy enforcement starts here:
  - Every query that returns organization data is scoped by user membership.
  - get_by_id_for_user() verifies the requesting user is actually a member
    before returning the org. This prevents horizontal privilege escalation
    (user A accessing user B's organization by guessing the UUID).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.organization import Organization
from app.db.models.user_organization import UserOrganization


class OrganizationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        """Raw lookup — callers must verify membership separately."""
        result = await self._db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self._db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        result = await self._db.execute(
            select(Organization.id).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none() is not None

    async def get_by_id_for_user(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Organization | None:
        """
        Returns the org only if the user is a member.
        This is the standard lookup used in protected routes.
        """
        result = await self._db.execute(
            select(Organization)
            .join(
                UserOrganization,
                (UserOrganization.organization_id == Organization.id)
                & (UserOrganization.user_id == user_id),
            )
            .where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[tuple[Organization, str]]:
        """
        Returns list of (organization, role) tuples for the given user.
        Used on the dashboard to show which orgs the user belongs to.
        """
        result = await self._db.execute(
            select(Organization, UserOrganization.role)
            .join(
                UserOrganization,
                (UserOrganization.organization_id == Organization.id)
                & (UserOrganization.user_id == user_id),
            )
            .order_by(Organization.name)
        )
        return result.all()

    async def create(self, name: str, slug: str) -> Organization:
        org = Organization(id=uuid.uuid4(), name=name, slug=slug)
        self._db.add(org)
        await self._db.flush()
        return org

    async def add_member(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str = "owner",
    ) -> UserOrganization:
        membership = UserOrganization(
            id=uuid.uuid4(),
            organization_id=org_id,
            user_id=user_id,
            role=role,
        )
        self._db.add(membership)
        await self._db.flush()
        return membership

    async def get_membership(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserOrganization | None:
        result = await self._db.execute(
            select(UserOrganization).where(
                UserOrganization.organization_id == org_id,
                UserOrganization.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
