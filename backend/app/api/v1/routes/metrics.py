"""
Metrics routes — with Redis cache injection.

The CacheService is constructed per-request from the shared Redis
connection pool (get_redis dependency). If Redis is unavailable,
CacheService is passed as None and MetricsApiService bypasses caching
gracefully — the response is computed from the DB exactly as before.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_service import CacheService
from app.core.dependencies import get_current_user, get_db
from app.core.redis_client import get_redis
from app.db.models.user import User
from app.schemas.metrics import (
    OverviewResponse,
    ServiceHealthResponse,
    ServiceMetricsResponse,
)
from app.services.metrics_api_service import MetricsApiService

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_WINDOW_MINUTES = {5, 15, 30, 60, 120, 240, 1440}


def _validated_window(window_minutes: int) -> int:
    if window_minutes not in VALID_WINDOW_MINUTES:
        return min(VALID_WINDOW_MINUTES, key=lambda v: abs(v - window_minutes))
    return window_minutes


def _get_cache() -> CacheService | None:
    """
    Build a CacheService from the module-level Redis client.
    Returns None if Redis is not yet initialised (app still starting up
    or Redis is down), which makes MetricsApiService skip caching.
    """
    try:
        redis = get_redis()
        return CacheService(redis)
    except RuntimeError:
        return None


@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Project metrics overview",
)
async def get_metrics_overview(
    org_id:     uuid.UUID,
    project_id: uuid.UUID,
    window_minutes: Annotated[int, Query(ge=5, le=1440)] = 60,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OverviewResponse:
    cache = _get_cache()
    return await MetricsApiService(db, cache).get_overview(
        org_id=org_id, project_id=project_id,
        user=current_user, window_minutes=_validated_window(window_minutes),
    )


@router.get(
    "/services/{service_id}/metrics",
    response_model=ServiceMetricsResponse,
    summary="Full metrics for one service",
)
async def get_service_metrics(
    org_id:     uuid.UUID,
    project_id: uuid.UUID,
    service_id: uuid.UUID,
    window_minutes: Annotated[int, Query(ge=5, le=1440)] = 60,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ServiceMetricsResponse:
    cache = _get_cache()
    return await MetricsApiService(db, cache).get_service_metrics(
        org_id=org_id, project_id=project_id, service_id=service_id,
        user=current_user, window_minutes=_validated_window(window_minutes),
    )


@router.get(
    "/services/{service_id}/health",
    response_model=ServiceHealthResponse,
    summary="Service health snapshot",
)
async def get_service_health(
    org_id:     uuid.UUID,
    project_id: uuid.UUID,
    service_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ServiceHealthResponse:
    cache = _get_cache()
    return await MetricsApiService(db, cache).get_service_health(
        org_id=org_id, project_id=project_id,
        service_id=service_id, user=current_user,
    )
