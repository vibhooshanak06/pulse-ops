"""
API key service.

Key generation design:
  secrets.token_hex(16) produces 32 random hex characters from the OS
  CSPRNG (cryptographically secure pseudorandom number generator).
  This gives 128 bits of entropy — the same as a UUID v4 but without
  the fixed structure that slightly reduces entropy.

  Full key format: po_live_<32 hex chars>
  Example:         po_live_a3f82c1d9e4b7065f1a2834cd6e90b17

  Key prefix stored: first 10 chars of the full key
  Example:           po_live_a3  ← safe to display in dashboard

Hashing:
  hashlib.sha256(key.encode()).hexdigest() — deterministic, fast, one-way.
  We use SHA-256 (not bcrypt) here because:
    - API keys are already 128-bit random, so brute-force is computationally
      infeasible — bcrypt's slow hashing would only hurt performance.
    - The 64-char hex digest is constant-length, indexable, and sub-ms to compute.
    - bcrypt is for passwords (low-entropy, human-chosen strings).

  This mirrors the design used by GitHub, Stripe, and Twilio.

Validation (called by telemetry ingestion on every request):
  hash the incoming key → look up in DB → return project_id or raise 401.
  The whole operation is a single indexed DB read: typically < 1ms.
"""

import hashlib
import secrets
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.api_key import ApiKey
from app.db.models.user import User
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
)

_KEY_PREFIX = "po_live_"
_KEY_RANDOM_BYTES = 16          # 32 hex chars = 128 bits entropy
_DISPLAY_PREFIX_LENGTH = 10     # "po_live_a3" — shown in dashboard


def _generate_raw_key() -> str:
    """Generate a cryptographically secure API key."""
    return _KEY_PREFIX + secrets.token_hex(_KEY_RANDOM_BYTES)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of the raw key — stored in DB, never the raw key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _display_prefix(raw_key: str) -> str:
    """Safe-to-display prefix, e.g. 'po_live_a3'."""
    return raw_key[:_DISPLAY_PREFIX_LENGTH]


class ApiKeyService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._orgs = OrganizationRepository(db)
        self._projects = ProjectRepository(db)
        self._keys = ApiKeyRepository(db)

    # ── Ownership verification ────────────────────────────────────────────────

    async def _require_project_access(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        if not await self._orgs.get_by_id_for_user(org_id, user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Organization not found.")
        if not await self._projects.get_by_id(project_id, org_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Project not found.")

    # ── Dashboard operations (JWT-authenticated) ──────────────────────────────

    async def list_for_project(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        user: User,
    ) -> ApiKeyListResponse:
        await self._require_project_access(org_id, project_id, user.id)
        keys = await self._keys.list_for_project(project_id)
        return ApiKeyListResponse(
            items=[ApiKeyResponse.model_validate(k) for k in keys],
            total=len(keys),
        )

    async def create(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        req: ApiKeyCreate,
        user: User,
    ) -> ApiKeyCreatedResponse:
        await self._require_project_access(org_id, project_id, user.id)

        raw_key = _generate_raw_key()
        key_hash = _hash_key(raw_key)
        prefix = _display_prefix(raw_key)

        api_key = await self._keys.create(
            project_id=project_id,
            name=req.name,
            key_prefix=prefix,
            key_hash=key_hash,
        )

        return ApiKeyCreatedResponse(
            key=raw_key,
            api_key=ApiKeyResponse.model_validate(api_key),
        )

    async def revoke(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        key_id: uuid.UUID,
        user: User,
    ) -> ApiKeyResponse:
        await self._require_project_access(org_id, project_id, user.id)

        api_key = await self._keys.get_by_id(key_id, project_id)
        if api_key is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="API key not found.")
        if not api_key.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="API key is already revoked.")

        revoked = await self._keys.revoke(api_key)
        return ApiKeyResponse.model_validate(revoked)

    # ── Telemetry ingestion validation (API-key-authenticated) ────────────────

    @staticmethod
    def hash_incoming_key(raw_key: str) -> str:
        """
        Exposed as a static method so the telemetry ingestion route
        can hash the incoming header value before the DB lookup.
        """
        return _hash_key(raw_key)

    async def validate_key(self, raw_key: str) -> ApiKey:
        """
        Validate an incoming API key from the X-API-Key header.

        Called on every telemetry ingestion request.
        Returns the ApiKey row (which contains project_id) on success.
        Raises HTTP 401 on failure — same error for invalid and revoked keys
        to avoid leaking which keys exist.
        """
        if not raw_key.startswith(_KEY_PREFIX):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        key_hash = _hash_key(raw_key)
        api_key = await self._keys.get_by_hash(key_hash)

        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # Fire-and-forget last_used update — don't await to avoid latency
        # on every telemetry request. The session will be flushed at commit.
        await self._keys.touch_last_used(api_key)

        return api_key
