"""
Project repository.

Projects are always scoped to an organization. Every query
includes the organization_id filter so cross-org data leakage
is impossible at the DB layer, not just in business logic.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project


class ProjectRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(
        self,
        project_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> Project | None:
        """Always scoped to org — prevents cross-org access."""
        result = await self._db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, org_id: uuid.UUID) -> list[Project]:
        result = await self._db.execute(
            select(Project)
            .where(Project.organization_id == org_id)
            .order_by(Project.name)
        )
        return list(result.scalars().all())

    async def slug_exists_in_org(self, org_id: uuid.UUID, slug: str) -> bool:
        result = await self._db.execute(
            select(Project.id).where(
                Project.organization_id == org_id,
                Project.slug == slug,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        org_id: uuid.UUID,
        name: str,
        slug: str,
        description: str | None = None,
    ) -> Project:
        project = Project(
            id=uuid.uuid4(),
            organization_id=org_id,
            name=name,
            slug=slug,
            description=description,
        )
        self._db.add(project)
        await self._db.flush()
        return project
