"""
Project routes.

All project routes are nested under /organizations/{org_id}/projects.
This URL structure makes the ownership hierarchy explicit in the API.

GET  /v1/organizations/{org_id}/projects            → list projects
POST /v1/organizations/{org_id}/projects            → create project
GET  /v1/organizations/{org_id}/projects/{proj_id}  → get one project
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse
from app.services.project_service import ProjectService

router = APIRouter()


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List projects in an organization",
)
async def list_projects(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    return await ProjectService(db).list_for_org(org_id, current_user)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=201,
    summary="Create a project",
)
async def create_project(
    org_id: uuid.UUID,
    req: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    return await ProjectService(db).create(org_id, req, current_user)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a project by ID",
)
async def get_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    return await ProjectService(db).get(org_id, project_id, current_user)
