"""
Telemetry repository.

bulk_insert is the core performance-critical operation.
Instead of N separate INSERT statements, we use SQLAlchemy Core's
insert() with a list of dicts — this compiles to a single
  INSERT INTO telemetry_events (col1, col2, ...) VALUES (...), (...), ...
statement. For a batch of 10 events that's 10x fewer round-trips to Postgres.

We use Core (not ORM) for bulk insert because ORM's session.add() adds
each object to the identity map and triggers per-row processing.
Core insert() bypasses the identity map entirely — pure SQL.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import insert, select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.telemetry_event import TelemetryEvent


class TelemetryRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def bulk_insert(self, rows: list[dict]) -> int:
        """
        Insert multiple telemetry events in a single SQL statement.
        Returns the number of rows inserted.

        Each dict in `rows` must contain all non-nullable TelemetryEvent columns.
        """
        if not rows:
            return 0
        await self._db.execute(insert(TelemetryEvent), rows)
        return len(rows)

    async def get_recent_for_service(
        self,
        service_id: uuid.UUID,
        minutes: int = 5,
        limit: int = 1000,
    ) -> list[TelemetryEvent]:
        """
        Fetch recent events for a service — used by the metrics engine
        to calculate aggregate windows.
        """
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = await self._db.execute(
            select(TelemetryEvent)
            .where(
                TelemetryEvent.service_id == service_id,
                TelemetryEvent.timestamp >= since,
            )
            .order_by(TelemetryEvent.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_for_endpoint(
        self,
        endpoint_id: uuid.UUID,
        minutes: int = 5,
        limit: int = 500,
    ) -> list[TelemetryEvent]:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = await self._db.execute(
            select(TelemetryEvent)
            .where(
                TelemetryEvent.endpoint_id == endpoint_id,
                TelemetryEvent.timestamp >= since,
            )
            .order_by(TelemetryEvent.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_for_service_in_window(
        self,
        service_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
    ) -> int:
        result = await self._db.execute(
            select(func.count(TelemetryEvent.id)).where(
                and_(
                    TelemetryEvent.service_id == service_id,
                    TelemetryEvent.timestamp >= window_start,
                    TelemetryEvent.timestamp < window_end,
                )
            )
        )
        return result.scalar_one() or 0
