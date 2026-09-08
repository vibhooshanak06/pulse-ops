"""
Organization routes.

GET  /v1/organizations           → list orgs the current user belongs to
POST /v1/organizations           → create a new org (user becomes owner)
GET  /v1/organizations/{org_id}  → get one org (must be a member)

All routes require a valid JWT — the Depends(get_current_user) dependency
handles token validation and user loading.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationWithRoleResponse,
)
from app.services.organization_service import OrganizationService

router = APIRouter()


@router.get(
    "",
    response_model=list[OrganizationWithRoleResponse],
    summary="List organizations for current user",
)
async def list_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationWithRoleResponse]:
    return await OrganizationService(db).list_for_user(current_user)


@router.post(
    "",
    response_model=OrganizationWithRoleResponse,
    status_code=201,
    summary="Create a new organization",
)
async def create_organization(
    req: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationWithRoleResponse:
    return await OrganizationService(db).create(req, current_user)


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get an organization by ID",
)
async def get_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    return await OrganizationService(db).get(org_id, current_user)
