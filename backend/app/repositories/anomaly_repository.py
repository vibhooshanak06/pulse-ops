"""
Anomaly repository.

Key query patterns:

  1. create()               — write a new detected anomaly
  2. get_unassigned_recent() — correlator reads these to group into incidents
  3. get_for_service()      — dashboard reads recent anomalies per service
  4. get_active_for_project() — overview dashboard: count of active anomalies
  5. resolve()              — mark anomaly resolved when metric returns to normal

Deduplication strategy:
  A new anomaly is only written if there is NO existing unresolved anomaly
  for the same (service_id, metric_type) combination. This prevents the
  detection engine from flooding the DB with duplicate anomaly rows when
  the same condition persists across multiple 1-minute windows.

  Instead, an ongoing anomaly is "already recorded" — the incident correlation
  engine in Phase 10 will track its duration via the incident timeline.
  A new anomaly row is only created when a metric_type transitions from
  "normal" to "anomalous" (rising edge), not on every anomalous window.

Why not UPDATE the existing row?
  INSERT-only gives us an immutable audit trail — every anomaly detection
  event is preserved. If we update, we lose the history of how the score
  changed over the duration of an incident.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.anomaly import Anomaly
from app.db.models.service import Service


class AnomalyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        service_id:          uuid.UUID,
        endpoint_id:         uuid.UUID | None,
        metric_aggregate_id: uuid.UUID | None,
        metric_type:         str,
        baseline_value:      float,
        current_value:       float,
        deviation_percent:   float,
        statistical_score:   float,
        ml_score:            float,
        combined_score:      float,
        severity:            str,
        detected_at:         datetime,
    ) -> Anomaly:
        anomaly = Anomaly(
            id                  = uuid.uuid4(),
            service_id          = service_id,
            endpoint_id         = endpoint_id,
            metric_aggregate_id = metric_aggregate_id,
            incident_id         = None,   # assigned by correlator in Phase 10
            metric_type         = metric_type,
            baseline_value      = baseline_value,
            current_value       = current_value,
            deviation_percent   = deviation_percent,
            statistical_score   = statistical_score,
            ml_score            = ml_score,
            combined_score      = combined_score,
            severity            = severity,
            detected_at         = detected_at,
            resolved_at         = None,
        )
        self._db.add(anomaly)
        await self._db.flush()
        return anomaly

    async def has_active_anomaly(
        self,
        service_id:  uuid.UUID,
        metric_type: str,
    ) -> bool:
        """
        Check if an unresolved anomaly already exists for this
        (service, metric_type) pair — used for deduplication.
        """
        result = await self._db.execute(
            select(Anomaly.id).where(
                Anomaly.service_id  == service_id,
                Anomaly.metric_type == metric_type,
                Anomaly.resolved_at.is_(None),
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_unassigned_recent(
        self,
        project_id:  uuid.UUID,
        since_minutes: int = 30,
    ) -> list[Anomaly]:
        """
        Fetch recent anomalies not yet assigned to an incident.
        Used by the correlation engine in Phase 10.
        Scoped to project via join through services.
        """
        since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        result = await self._db.execute(
            select(Anomaly)
            .join(Service, Service.id == Anomaly.service_id)
            .where(
                Service.project_id      == project_id,
                Anomaly.incident_id.is_(None),
                Anomaly.detected_at     >= since,
                Anomaly.resolved_at.is_(None),
            )
            .order_by(Anomaly.detected_at)
        )
        return list(result.scalars().all())

    async def get_for_service(
        self,
        service_id:    uuid.UUID,
        since_minutes: int = 60,
        include_resolved: bool = False,
    ) -> list[Anomaly]:
        """Fetch recent anomalies for one service — used by the dashboard."""
        since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        conditions = [
            Anomaly.service_id  == service_id,
            Anomaly.detected_at >= since,
        ]
        if not include_resolved:
            conditions.append(Anomaly.resolved_at.is_(None))

        result = await self._db.execute(
            select(Anomaly)
            .where(and_(*conditions))
            .order_by(Anomaly.detected_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_for_project(
        self,
        project_id: uuid.UUID,
    ) -> list[Anomaly]:
        """All unresolved anomalies in a project — for the overview badge count."""
        result = await self._db.execute(
            select(Anomaly)
            .join(Service, Service.id == Anomaly.service_id)
            .where(
                Service.project_id    == project_id,
                Anomaly.resolved_at.is_(None),
            )
            .order_by(Anomaly.detected_at.desc())
        )
        return list(result.scalars().all())

    async def resolve(
        self,
        service_id:  uuid.UUID,
        metric_type: str,
    ) -> int:
        """
        Mark all active anomalies for (service, metric_type) as resolved.
        Called when a metric returns to within normal range.
        Returns the count of resolved rows.
        """
        from sqlalchemy import update
        result = await self._db.execute(
            update(Anomaly)
            .where(
                Anomaly.service_id  == service_id,
                Anomaly.metric_type == metric_type,
                Anomaly.resolved_at.is_(None),
            )
            .values(resolved_at=datetime.now(timezone.utc))
        )
        await self._db.flush()
        return result.rowcount

    async def get_by_id(self, anomaly_id: uuid.UUID) -> Anomaly | None:
        result = await self._db.execute(
            select(Anomaly).where(Anomaly.id == anomaly_id)
        )
        return result.scalar_one_or_none()
