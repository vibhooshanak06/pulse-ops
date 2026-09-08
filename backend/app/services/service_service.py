"""
Service service (the business-logic layer for the Service model).

Services sit under projects. The verification chain is:
  user → org membership → project belongs to org → service belongs to project

This three-level chain ensures:
  - User A cannot access Org B's projects
  - User A cannot access Project X's services if Project X is in Org B
  even if they know the exact UUID of the service.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.service_repository import ServiceRepository
from app.schemas.service import ServiceCreate, ServiceListResponse, ServiceResponse


class ServiceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._orgs = OrganizationRepository(db)
        self._projects = ProjectRepository(db)
        self._services = ServiceRepository(db)

    async def _require_project_access(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Verifies user ∈ org and project ∈ org."""
        org = await self._orgs.get_by_id_for_user(org_id, user_id)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found.",
            )
        project = await self._projects.get_by_id(project_id, org_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

    async def list_for_project(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        user: User,
    ) -> ServiceListResponse:
        await self._require_project_access(org_id, project_id, user.id)
        services = await self._services.list_for_project(project_id)
        return ServiceListResponse(
            items=[ServiceResponse.model_validate(s) for s in services],
            total=len(services),
        )

    async def get(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        service_id: uuid.UUID,
        user: User,
    ) -> ServiceResponse:
        await self._require_project_access(org_id, project_id, user.id)
        service = await self._services.get_by_id(service_id, project_id)
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )
        return ServiceResponse.model_validate(service)

    async def create(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        req: ServiceCreate,
        user: User,
    ) -> ServiceResponse:
        await self._require_project_access(org_id, project_id, user.id)

        if await self._services.name_exists_in_project(project_id, req.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A service named '{req.name}' already exists in this project.",
            )

        service = await self._services.create(
            project_id=project_id,
            name=req.name,
            description=req.description,
        )
        return ServiceResponse.model_validate(service)
