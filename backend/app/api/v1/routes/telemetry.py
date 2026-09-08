"""
Telemetry ingestion route.

POST /v1/telemetry

Authentication: X-API-Key header (project API key, not JWT).

This is the only endpoint in the system that accepts API key auth.
Every other endpoint uses JWT Bearer tokens.

Why a top-level /v1/telemetry instead of nesting under /organizations/.../telemetry?
  The SDK only knows its API key — it has no concept of org or project IDs.
  The API key itself carries the project context (api_key.project_id).
  A flat URL also minimises the SDK configuration surface:
  the user only needs to set ingestion_url + api_key, not a full org/project path.

Response 202 Accepted:
  We return 202 (not 200) to signal "received and will process" rather than
  "processed synchronously". In V2 when we add Kafka, the ingestion endpoint
  enqueues events and the 202 becomes even more accurate.
"""

import logging

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.dependencies import get_db
from app.schemas.telemetry import TelemetryBatchRequest, TelemetryBatchResponse
from app.services.telemetry_service import TelemetryIngestionService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "",
    response_model=TelemetryBatchResponse,
    status_code=202,
    summary="Ingest telemetry events",
    description=(
        "Accepts a batch of API telemetry events from the PulseOps SDK. "
        "Authenticate with the project API key in the `X-API-Key` header. "
        "Returns 202 Accepted with counts of stored events."
    ),
)
async def ingest_telemetry(
    batch: TelemetryBatchRequest,
    x_api_key: str = Header(
        ...,
        alias="X-API-Key",
        description="Project API key generated in the PulseOps dashboard.",
    ),
    db: AsyncSession = Depends(get_db),
) -> TelemetryBatchResponse:
    logger.debug(
        "Telemetry batch received: service=%s events=%d",
        batch.service_name,
        len(batch.events),
    )
    return await TelemetryIngestionService(db).ingest(
        raw_api_key=x_api_key,
        batch=batch,
    )
