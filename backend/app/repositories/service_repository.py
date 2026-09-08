"""
Service repository.

Services are scoped to projects. The get_by_id method requires project_id
to prevent a user guessing a service UUID and accessing another org's service.

The `get_or_create_by_name` method is used by the telemetry ingestion pipeline
(Phase 5) to automatically register services the first time telemetry arrives.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.service import Service


class ServiceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(
        self,
        service_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> Service | None:
        """Scoped to project — prevents cross-project access."""
        result = await self._db.execute(
            select(Service).where(
                Service.id == service_id,
                Service.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_any_project(self, service_id: uuid.UUID) -> Service | None:
        """
        Used by the anomaly/incident engines which already have a verified
        project context. Avoids a redundant project_id join in those paths.
        """
        result = await self._db.execute(
            select(Service).where(Service.id == service_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        project_id: uuid.UUID,
        name: str,
    ) -> Service | None:
        result = await self._db.execute(
            select(Service).where(
                Service.project_id == project_id,
                Service.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_project(self, project_id: uuid.UUID) -> list[Service]:
        result = await self._db.execute(
            select(Service)
            .where(Service.project_id == project_id)
            .order_by(Service.name)
        )
        return list(result.scalars().all())

    async def name_exists_in_project(
        self,
        project_id: uuid.UUID,
        name: str,
    ) -> bool:
        result = await self._db.execute(
            select(Service.id).where(
                Service.project_id == project_id,
                Service.name == name,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        project_id: uuid.UUID,
        name: str,
        description: str | None = None,
    ) -> Service:
        service = Service(
            id=uuid.uuid4(),
            project_id=project_id,
            name=name,
            description=description,
            health_status="unknown",
        )
        self._db.add(service)
        await self._db.flush()
        return service

    async def get_or_create_by_name(
        self,
        project_id: uuid.UUID,
        name: str,
    ) -> tuple[Service, bool]:
        """
        Returns (service, created) — used by telemetry ingestion to
        auto-register services. `created` is True on first appearance.
        """
        service = await self.get_by_name(project_id, name)
        if service:
            return service, False
        service = await self.create(project_id, name)
        return service, True

    async def update_health_and_last_seen(
        self,
        service_id: uuid.UUID,
        health_status: str,
    ) -> None:
        """Called by the metrics engine after each aggregation cycle."""
        result = await self._db.execute(
            select(Service).where(Service.id == service_id)
        )
        service = result.scalar_one_or_none()
        if service:
            service.health_status = health_status
            service.last_seen_at = datetime.now(timezone.utc)
