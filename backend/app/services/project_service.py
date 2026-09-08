"""
Project service.

Projects sit under organizations. Every project operation first
verifies the user is a member of the parent organization, then
operates within that org's scope.

This two-step verification pattern is used throughout:
  1. org_repo.get_by_id_for_user() → confirms user ∈ org
  2. project_repo.get_by_id(org_id=org.id) → confirms project ∈ org
"""

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectResponse


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug.strip("-") or "project"


class ProjectService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._orgs = OrganizationRepository(db)
        self._projects = ProjectRepository(db)

    async def _require_org_access(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        org = await self._orgs.get_by_id_for_user(org_id, user_id)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )

    async def list_for_org(
        self,
        org_id: uuid.UUID,
        user: User,
    ) -> list[ProjectResponse]:
        await self._require_org_access(org_id, user.id)
        projects = await self._projects.list_for_org(org_id)
        return [ProjectResponse.model_validate(p) for p in projects]

    async def get(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        user: User,
    ) -> ProjectResponse:
        await self._require_org_access(org_id, user.id)
        project = await self._projects.get_by_id(project_id, org_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return ProjectResponse.model_validate(project)

    async def create(
        self,
        org_id: uuid.UUID,
        req: ProjectCreate,
        user: User,
    ) -> ProjectResponse:
        await self._require_org_access(org_id, user.id)

        # Determine and deduplicate slug
        base_slug = req.slug if req.slug else _slugify(req.name)
        slug = base_slug
        if await self._projects.slug_exists_in_org(org_id, slug):
            for i in range(2, 100):
                candidate = f"{base_slug}-{i}"
                if not await self._projects.slug_exists_in_org(org_id, candidate):
                    slug = candidate
                    break

        project = await self._projects.create(
            org_id=org_id,
            name=req.name,
            slug=slug,
            description=req.description,
        )
        return ProjectResponse.model_validate(project)
