"""
API key routes.

Nested under projects — a key is always scoped to one project.

GET    /v1/organizations/{org_id}/projects/{proj_id}/api-keys           → list
POST   /v1/organizations/{org_id}/projects/{proj_id}/api-keys           → create (returns key once)
DELETE /v1/organizations/{org_id}/projects/{proj_id}/api-keys/{key_id}  → revoke
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
)
from app.services.api_key_service import ApiKeyService

router = APIRouter()


@router.get(
    "",
    response_model=ApiKeyListResponse,
    summary="List API keys for a project",
)
async def list_api_keys(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyListResponse:
    return await ApiKeyService(db).list_for_project(org_id, project_id, current_user)


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=201,
    summary="Create an API key",
    description=(
        "Generates a new API key for telemetry ingestion. "
        "The full key is returned **once** in the response — store it immediately. "
        "It cannot be retrieved again after this request."
    ),
)
async def create_api_key(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    req: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreatedResponse:
    return await ApiKeyService(db).create(org_id, project_id, req, current_user)


@router.delete(
    "/{key_id}",
    response_model=ApiKeyResponse,
    summary="Revoke an API key",
    description=(
        "Revokes an API key immediately. "
        "Any telemetry sent using this key after revocation will be rejected. "
        "Revocation is permanent — the key cannot be re-activated."
    ),
)
async def revoke_api_key(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyResponse:
    return await ApiKeyService(db).revoke(org_id, project_id, key_id, current_user)
