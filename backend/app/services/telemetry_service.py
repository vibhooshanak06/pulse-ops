"""
Telemetry ingestion service.

Pipeline for every POST /v1/telemetry request:

  1. Validate the API key  →  resolve project_id
  2. Get-or-create Service by (project_id, service_name)
  3. For each unique (endpoint_path, method) in the batch:
       get-or-create Endpoint row
  4. Build a list of TelemetryEvent dicts with all FK IDs resolved
  5. Bulk-insert all events in one SQL statement
  6. Update service.last_seen_at

Step 3 batches endpoint lookups:
  We deduplicate the (path, method) pairs in the batch before hitting the DB,
  so a batch of 100 events all from the same endpoint does exactly ONE
  get_or_create call, not 100.

Step 4 sets is_error = status_code >= 400.
  This denormalised flag exists so the metrics engine can do:
    COUNT(*) FILTER (WHERE is_error) / COUNT(*)
  without a per-row function call.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.endpoint_repository import EndpointRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.telemetry_repository import TelemetryRepository
from app.schemas.telemetry import TelemetryBatchRequest, TelemetryBatchResponse
from app.services.api_key_service import ApiKeyService


class TelemetryIngestionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._api_keys  = ApiKeyRepository(db)
        self._services  = ServiceRepository(db)
        self._endpoints = EndpointRepository(db)
        self._telemetry = TelemetryRepository(db)

    async def ingest(
        self,
        raw_api_key: str,
        batch: TelemetryBatchRequest,
    ) -> TelemetryBatchResponse:

        # ── 1. Validate API key → resolve project_id ─────────────────────────
        api_key_svc = ApiKeyService(self._db)
        api_key     = await api_key_svc.validate_key(raw_api_key)
        project_id  = api_key.project_id

        # ── 2. Resolve / auto-create service ─────────────────────────────────
        service, _ = await self._services.get_or_create_by_name(
            project_id=project_id,
            name=batch.service_name,
        )

        # ── 3. Resolve unique endpoints in batch (deduplicated) ───────────────
        # Build a set of unique (path, method) pairs first — avoids N DB calls
        # for a batch where every event hits the same endpoint.
        unique_endpoints: dict[tuple[str, str], uuid.UUID] = {}

        for event in batch.events:
            key = (event.endpoint, event.method)
            if key not in unique_endpoints:
                endpoint, _ = await self._endpoints.get_or_create(
                    service_id=service.id,
                    path=event.endpoint,
                    method=event.method,
                )
                unique_endpoints[key] = endpoint.id

        # ── 4. Build rows for bulk insert ─────────────────────────────────────
        rows: list[dict] = []
        for event in batch.events:
            endpoint_id = unique_endpoints[(event.endpoint, event.method)]
            rows.append({
                "id":            uuid.uuid4(),
                "service_id":    service.id,
                "endpoint_id":   endpoint_id,
                "endpoint_path": event.endpoint,
                "method":        event.method,
                "status_code":   event.status_code,
                "latency_ms":    event.latency_ms,
                "is_error":      event.status_code >= 400,
                "timestamp":     event.timestamp,
                "received_at":   datetime.now(timezone.utc),
            })

        # ── 5. Bulk insert ────────────────────────────────────────────────────
        accepted = await self._telemetry.bulk_insert(rows)

        # ── 6. Touch service last_seen_at ─────────────────────────────────────
        await self._services.update_health_and_last_seen(
            service_id=service.id,
            health_status=service.health_status,   # keep existing status; metrics engine updates this
        )

        return TelemetryBatchResponse(
            accepted=accepted,
            rejected=0,
            service_id=str(service.id),
        )
