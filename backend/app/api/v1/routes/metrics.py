"""
Metrics routes.

URL structure:
  GET /v1/organizations/{org_id}/projects/{project_id}/metrics/overview
      → summary across all services in the project

  GET /v1/organizations/{org_id}/projects/{project_id}/services/{service_id}/metrics
      → full time-series + endpoint table for one service

  GET /v1/organizations/{org_id}/projects/{project_id}/services/{service_id}/health
      → lightweight health snapshot (used by service list / sidebar)

Query parameters:
  window_minutes  — how many minutes of history to include (default 60)
                    Valid values: 5, 15, 30, 60, 120, 240, 1440 (24h)

Why metrics endpoints live under org/project:
  Every metrics query is scoped to a project. The service layer enforces
  that the requesting user is a member of the org. Without this nesting,
  a user could query metrics for a service in someone else's project by
  guessing the service UUID.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.metrics import (
    OverviewResponse,
    ServiceHealthResponse,
    ServiceMetricsResponse,
)
from app.services.metrics_api_service import MetricsApiService

router = APIRouter()

# Valid time windows — prevents clients from requesting absurdly large ranges
# that would trigger very slow aggregation passes.
VALID_WINDOW_MINUTES = {5, 15, 30, 60, 120, 240, 1440}


def _validated_window(window_minutes: int) -> int:
    if window_minutes not in VALID_WINDOW_MINUTES:
        # Snap to nearest valid window rather than erroring —
        # friendlier for dashboard clients that pass arbitrary values.
        return min(VALID_WINDOW_MINUTES, key=lambda v: abs(v - window_minutes))
    return window_minutes


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get(
    "/overview",
    response_model=OverviewResponse,
    summary="Project metrics overview",
    description=(
        "Returns aggregated health and metrics across all services in the project. "
        "Triggers on-demand aggregation for any un-processed telemetry windows."
    ),
)
async def get_metrics_overview(
    org_id:     uuid.UUID,
    project_id: uuid.UUID,
    window_minutes: Annotated[int, Query(ge=5, le=1440)] = 60,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OverviewResponse:
    wm = _validated_window(window_minutes)
    return await MetricsApiService(db).get_overview(
        org_id=org_id,
        project_id=project_id,
        user=current_user,
        window_minutes=wm,
    )


# ── Service metrics (full time-series) ────────────────────────────────────────

@router.get(
    "/services/{service_id}/metrics",
    response_model=ServiceMetricsResponse,
    summary="Full metrics for one service",
    description=(
        "Returns time-series metric windows, current snapshot, and "
        "per-endpoint performance table for a single service. "
        "Triggers on-demand aggregation before responding."
    ),
)
async def get_service_metrics(
    org_id:     uuid.UUID,
    project_id: uuid.UUID,
    service_id: uuid.UUID,
    window_minutes: Annotated[int, Query(ge=5, le=1440)] = 60,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ServiceMetricsResponse:
    wm = _validated_window(window_minutes)
    return await MetricsApiService(db).get_service_metrics(
        org_id=org_id,
        project_id=project_id,
        service_id=service_id,
        user=current_user,
        window_minutes=wm,
    )


# ── Service health snapshot (lightweight) ─────────────────────────────────────

@router.get(
    "/services/{service_id}/health",
    response_model=ServiceHealthResponse,
    summary="Service health snapshot",
    description=(
        "Lightweight health snapshot for a single service. "
        "Uses pre-computed aggregates — does not trigger re-aggregation. "
        "Suitable for polling from the service list or sidebar."
    ),
)
async def get_service_health(
    org_id:     uuid.UUID,
    project_id: uuid.UUID,
    service_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ServiceHealthResponse:
    return await MetricsApiService(db).get_service_health(
        org_id=org_id,
        project_id=project_id,
        service_id=service_id,
        user=current_user,
    )
