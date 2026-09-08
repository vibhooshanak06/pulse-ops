"""
Endpoint repository.

The get_or_create pattern is the critical piece here.
On every telemetry batch we may see endpoints the system has never seen before.
We need to resolve them to DB rows without creating duplicates under concurrent load.

Race condition handling:
  Two SDK instances sending the first request to the same endpoint simultaneously
  would both try to INSERT — one succeeds, one hits the UNIQUE constraint.
  We handle this with an upsert pattern:
    INSERT ... ON CONFLICT (service_id, path, method) DO NOTHING
    followed by a SELECT to get the existing row.

  SQLAlchemy's insert().on_conflict_do_nothing() maps directly to PostgreSQL's
  ON CONFLICT DO NOTHING — atomic and safe under concurrent writes.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.endpoint import Endpoint


class EndpointRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_service_path_method(
        self,
        service_id: uuid.UUID,
        path: str,
        method: str,
    ) -> Endpoint | None:
        result = await self._db.execute(
            select(Endpoint).where(
                Endpoint.service_id == service_id,
                Endpoint.path == path,
                Endpoint.method == method,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        service_id: uuid.UUID,
        path: str,
        method: str,
    ) -> tuple[Endpoint, bool]:
        """
        Returns (endpoint, created).
        Uses upsert to handle concurrent inserts safely.
        """
        new_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # Attempt upsert — INSERT ... ON CONFLICT DO NOTHING
        stmt = (
            pg_insert(Endpoint)
            .values(
                id=new_id,
                service_id=service_id,
                path=path,
                method=method,
                created_at=now,
                last_seen_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=None,
                constraint="uq_endpoint_service_path_method",
            )
        )
        result = await self._db.execute(stmt)
        created = result.rowcount > 0

        # Fetch the row — either the one we just inserted or the existing one
        endpoint = await self.get_by_service_path_method(service_id, path, method)
        return endpoint, created

    async def touch_last_seen(
        self,
        endpoint_id: uuid.UUID,
    ) -> None:
        result = await self._db.execute(
            select(Endpoint).where(Endpoint.id == endpoint_id)
        )
        ep = result.scalar_one_or_none()
        if ep:
            ep.last_seen_at = datetime.now(timezone.utc)
