"""
Telemetry ingestion route — with Redis rate limiting.

Rate limiting design:
  Identifier: SHA-256 hash of the API key (already computed during auth,
              but we re-hash here so the rate limit key never contains the
              plain-text key, even in Redis).
  Window:     1 minute (60 seconds)
  Limit:      Configurable via TELEMETRY_RATE_LIMIT_PER_MINUTE env var (default 1000)
  Response on breach: HTTP 429 Too Many Requests

Why hash the key for the rate-limit identifier?
  The raw API key is a secret. We never want it appearing in Redis keys,
  log files, or error messages. The hash is deterministic and unique —
  perfect as an identifier without exposing the secret.

Fail-open on Redis unavailability:
  CacheService.check_rate_limit() returns (True, 0) when Redis is down.
  This means telemetry ingestion continues uninterrupted even if Redis
  goes offline — we accept a small window of unprotected traffic rather
  than dropping all telemetry from every SDK in the system.

Rate limit headers:
  We return X-RateLimit-Limit and X-RateLimit-Remaining so SDK clients
  (and developers debugging) can see their current consumption.
"""

import hashlib
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_service import CacheService
from app.core.config import settings
from app.core.dependencies import get_db
from app.core.redis_client import get_redis
from app.schemas.telemetry import TelemetryBatchRequest, TelemetryBatchResponse
from app.services.telemetry_service import TelemetryIngestionService

logger = logging.getLogger(__name__)
router = APIRouter()


def _rate_limit_id(raw_api_key: str) -> str:
    """
    Derive a stable, non-secret rate-limit identifier from the API key.
    We use the first 16 chars of the SHA-256 hex digest — short enough to
    keep Redis key sizes small, long enough to be collision-resistant for
    the number of API keys a platform handles.
    """
    return hashlib.sha256(raw_api_key.encode()).hexdigest()[:16]


def _get_cache() -> CacheService | None:
    try:
        return CacheService(get_redis())
    except RuntimeError:
        return None


@router.post(
    "",
    response_model=TelemetryBatchResponse,
    status_code=202,
    summary="Ingest telemetry events",
    description=(
        "Accepts a batch of API telemetry events from the PulseOps SDK. "
        "Authenticate with the project API key in the `X-API-Key` header. "
        "Rate limited to TELEMETRY_RATE_LIMIT_PER_MINUTE requests per minute per key."
    ),
)
async def ingest_telemetry(
    batch: TelemetryBatchRequest,
    response: Response,
    x_api_key: str = Header(
        ...,
        alias="X-API-Key",
        description="Project API key generated in the PulseOps dashboard.",
    ),
    db: AsyncSession = Depends(get_db),
) -> TelemetryBatchResponse:

    limit = settings.TELEMETRY_RATE_LIMIT_PER_MINUTE

    # ── Rate limit check ──────────────────────────────────────────────────────
    cache = _get_cache()
    if cache is not None:
        identifier   = _rate_limit_id(x_api_key)
        allowed, count = await cache.check_rate_limit(
            identifier=identifier,
            limit=limit,
        )

        # Always attach rate limit headers so clients can self-monitor
        response.headers["X-RateLimit-Limit"]     = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))

        if not allowed:
            logger.warning(
                "Rate limit exceeded: identifier=%s count=%d limit=%d",
                identifier, count, limit,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: {count} requests in the current "
                    f"window (limit {limit}/min). "
                    "Reduce your SDK flush frequency or batch size."
                ),
                headers={
                    "X-RateLimit-Limit":     str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After":           "60",
                },
            )
    else:
        # Redis unavailable — skip rate limiting, log so we can track it
        logger.debug("Rate limiting skipped: Redis unavailable")

    # ── Ingest ────────────────────────────────────────────────────────────────
    logger.debug(
        "Telemetry batch: service=%s events=%d",
        batch.service_name, len(batch.events),
    )
    return await TelemetryIngestionService(db).ingest(
        raw_api_key=x_api_key,
        batch=batch,
    )
