"""
Anomaly routes.

GET /v1/organizations/{org_id}/projects/{project_id}/anomalies
    → all active anomalies across the project (for overview badge + list)

GET /v1/organizations/{org_id}/projects/{project_id}/services/{service_id}/anomalies
    → anomalies for one specific service

Both endpoints trigger on-demand detection before returning results,
so the dashboard always shows up-to-date anomaly state without needing
a background scheduler (though Phase 9's runner adds one too).

Query params:
  include_resolved  — include resolved anomalies (default False)
  since_minutes     — look-back window (default 60)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.repositories.anomaly_repository import AnomalyRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.service_repository import ServiceRepository
from app.schemas.anomaly import AnomalyListResponse, AnomalyResponse
from app.services.anomaly_detection_service import AnomalyDetectionService

router = APIRouter()


async def _check_project_access(
    org_id:     uuid.UUID,
    project_id: uuid.UUID,
    user_id:    uuid.UUID,
    db:         AsyncSession,
) -> None:
    orgs = OrganizationRepository(db)
    if not await orgs.get_by_id_for_user(org_id, user_id):
        raise HTTPException(status_code=404, detail="Organization not found.")
    projs = ProjectRepository(db)
    if not await projs.get_by_id(project_id, org_id):
        raise HTTPException(status_code=404, detail="Project not found.")


@router.get(
    "",
    response_model=AnomalyListResponse,
    summary="List anomalies across a project",
    description=(
        "Returns active (and optionally resolved) anomalies for all services "
        "in the project. Triggers on-demand detection before responding."
    ),
)
async def list_project_anomalies(
    org_id:     uuid.UUID,
    project_id: uuid.UUID,
    include_resolved: Annotated[bool, Query()] = False,
    since_minutes:    Annotated[int, Query(ge=5, le=1440)] = 60,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnomalyListResponse:
    await _check_project_access(org_id, project_id, current_user.id, db)

    # Trigger on-demand detection across all project services
    detector = AnomalyDetectionService(db)
    await detector.detect_for_project(project_id)

    anomaly_repo = AnomalyRepository(db)
    anomalies    = await anomaly_repo.get_active_for_project(project_id)

    # If include_resolved, also fetch resolved anomalies per service
    if include_resolved:
        svcs = await ServiceRepository(db).list_for_project(project_id)
        seen = {a.id for a in anomalies}
        for svc in svcs:
            resolved = await anomaly_repo.get_for_service(
                svc.id, since_minutes=since_minutes, include_resolved=True
            )
            for r in resolved:
                if r.id not in seen:
                    anomalies.append(r)
                    seen.add(r.id)

    active_count = sum(1 for a in anomalies if a.resolved_at is None)

    return AnomalyListResponse(
        items  = [AnomalyResponse.model_validate(a) for a in anomalies],
        total  = len(anomalies),
        active = active_count,
    )


@router.get(
    "/services/{service_id}",
    response_model=AnomalyListResponse,
    summary="List anomalies for one service",
)
async def list_service_anomalies(
    org_id:     uuid.UUID,
    project_id: uuid.UUID,
    service_id: uuid.UUID,
    include_resolved: Annotated[bool, Query()] = False,
    since_minutes:    Annotated[int, Query(ge=5, le=1440)] = 60,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnomalyListResponse:
    await _check_project_access(org_id, project_id, current_user.id, db)

    svc_repo = ServiceRepository(db)
    service  = await svc_repo.get_by_id(service_id, project_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found.")

    # Trigger on-demand detection for this service
    detector = AnomalyDetectionService(db)
    await detector.detect_for_service(service_id)

    anomaly_repo = AnomalyRepository(db)
    anomalies    = await anomaly_repo.get_for_service(
        service_id,
        since_minutes=since_minutes,
        include_resolved=include_resolved,
    )
    active_count = sum(1 for a in anomalies if a.resolved_at is None)

    return AnomalyListResponse(
        items  = [AnomalyResponse.model_validate(a) for a in anomalies],
        total  = len(anomalies),
        active = active_count,
    )
