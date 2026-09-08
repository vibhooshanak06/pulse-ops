"""
API key repository.

The single most performance-critical query here is get_by_hash() —
it runs on EVERY telemetry ingestion request. The ix_api_keys_key_hash
index (created in Phase 2) makes this a sub-millisecond lookup.

Soft-delete pattern:
  We never DELETE api_key rows. We set is_active=False and revoked_at=now().
  This preserves the audit trail: "this key was revoked at 14:32 on Aug 30".
  Hard-deleting would make it impossible to audit which key sent which telemetry.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.api_key import ApiKey


class ApiKeyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        """
        Primary telemetry auth lookup.
        Only returns active keys — revoked keys return None.
        """
        result = await self._db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        key_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> ApiKey | None:
        """Scoped to project — prevents cross-project key access."""
        result = await self._db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_project(self, project_id: uuid.UUID) -> list[ApiKey]:
        result = await self._db.execute(
            select(ApiKey)
            .where(ApiKey.project_id == project_id)
            .order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        project_id: uuid.UUID,
        name: str,
        key_prefix: str,
        key_hash: str,
    ) -> ApiKey:
        api_key = ApiKey(
            id=uuid.uuid4(),
            project_id=project_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            is_active=True,
        )
        self._db.add(api_key)
        await self._db.flush()
        return api_key

    async def revoke(self, api_key: ApiKey) -> ApiKey:
        """Soft-delete: mark inactive and record revocation time."""
        api_key.is_active = False
        api_key.revoked_at = datetime.now(timezone.utc)
        await self._db.flush()
        return api_key

    async def touch_last_used(self, api_key: ApiKey) -> None:
        """
        Update last_used_at on successful telemetry auth.
        Called asynchronously — a missed update is acceptable,
        so we do not raise if this flush fails.
        """
        api_key.last_used_at = datetime.now(timezone.utc)
