"""
Organization service.

Multi-tenancy rule enforced here:
  Every operation that touches an organization first calls
  _require_membership() which raises HTTP 404 if the user
  is not a member of that org.

  We return 404 (not 403) intentionally — revealing that an
  org exists to an unauthorized user is itself an information leak.
  "Not found" is the correct response for resources the user cannot access.
"""

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization
from app.db.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationWithRoleResponse,
)


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug.strip("-") or "org"


class OrganizationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = OrganizationRepository(db)

    async def _require_membership(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Organization:
        """
        Returns the org if user is a member, raises HTTP 404 otherwise.
        This is the primary multi-tenancy enforcement gate.
        """
        org = await self._repo.get_by_id_for_user(org_id, user_id)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )
        return org

    async def list_for_user(
        self, user: User
    ) -> list[OrganizationWithRoleResponse]:
        rows = await self._repo.list_for_user(user.id)
        return [
            OrganizationWithRoleResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                created_at=org.created_at,
                role=role,
            )
            for org, role in rows
        ]

    async def get(
        self,
        org_id: uuid.UUID,
        user: User,
    ) -> OrganizationResponse:
        org = await self._require_membership(org_id, user.id)
        return OrganizationResponse.model_validate(org)

    async def create(
        self,
        req: OrganizationCreate,
        user: User,
    ) -> OrganizationWithRoleResponse:
        # Determine slug
        base_slug = req.slug if req.slug else _slugify(req.name)
        # Ensure uniqueness
        slug = base_slug
        if await self._repo.slug_exists(slug):
            for i in range(2, 100):
                candidate = f"{base_slug}-{i}"
                if not await self._repo.slug_exists(candidate):
                    slug = candidate
                    break

        org = await self._repo.create(name=req.name, slug=slug)
        await self._repo.add_member(org_id=org.id, user_id=user.id, role="owner")

        return OrganizationWithRoleResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            created_at=org.created_at,
            role="owner",
        )
