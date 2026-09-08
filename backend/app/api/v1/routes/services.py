"""
Service routes.

Nested under projects:
GET  /v1/organizations/{org_id}/projects/{proj_id}/services            → list
POST /v1/organizations/{org_id}/projects/{proj_id}/services            → create
GET  /v1/organizations/{org_id}/projects/{proj_id}/services/{svc_id}   → get one

The deep nesting might look verbose but it enforces the hierarchy
in the URL itself — every route carries its full ownership context.
Dashboard API clients always know exactly which org/project they're in.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.service import ServiceCreate, ServiceListResponse, ServiceResponse
from app.services.service_service import ServiceService

router = APIRouter()


@router.get(
    "",
    response_model=ServiceListResponse,
    summary="List services in a project",
)
async def list_services(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ServiceListResponse:
    return await ServiceService(db).list_for_project(org_id, project_id, current_user)


@router.post(
    "",
    response_model=ServiceResponse,
    status_code=201,
    summary="Create a service",
)
async def create_service(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    req: ServiceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ServiceResponse:
    return await ServiceService(db).create(org_id, project_id, req, current_user)


@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Get a service by ID",
)
async def get_service(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    service_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ServiceResponse:
    return await ServiceService(db).get(org_id, project_id, service_id, current_user)
