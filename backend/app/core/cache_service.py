"""
Cache service — the single abstraction over Redis for all caching operations.

Design principles:
  1. NEVER let a cache failure crash a request. Every Redis call is wrapped
     in try/except. If Redis is down, callers fall through to the DB.
  2. Serialize/deserialize with JSON — readable, debuggable, no pickle risks.
  3. Cache keys are deterministic and documented — no magic strings scattered
     across the codebase.
  4. TTLs are intentionally short in V1 (30–60s). It is better to occasionally
     recompute than to serve stale metrics that mislead engineers.

Cache key strategy:
  metrics:overview:{project_id}:{window_minutes}
  metrics:service:{service_id}:{window_minutes}
  health:{service_id}

Why not cache telemetry events?
  Telemetry events are write-heavy and read rarely (only by the aggregation
  engine, which runs once per minute). Caching them would burn Redis memory
  for zero dashboard benefit.

Why 30s TTL for metrics?
  The metrics engine runs at 1-minute granularity. A 30s cache means at most
  one dashboard refresh sees slightly stale data before the cache refreshes —
  acceptable for an observability dashboard. Sub-second SLA is not required.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ── TTL constants ─────────────────────────────────────────────────────────────
METRICS_CACHE_TTL_SECONDS    = 30
HEALTH_SNAPSHOT_TTL_SECONDS  = 60
RATE_LIMIT_WINDOW_SECONDS    = 60   # 1-minute sliding window


class CacheService:
    """
    Async Redis cache service.

    All methods are fire-safe: if Redis is unavailable, they log a warning
    and return None/False rather than raising. Callers handle the None case
    by falling back to the database.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    # ── Generic get/set/delete ────────────────────────────────────────────────

    async def get(self, key: str) -> Any | None:
        """
        Fetch a cached value by key.
        Returns the deserialized Python object, or None on miss/error.
        """
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Cache GET failed for key=%s: %s", key, exc)
            return None

    async def set(self, key: str, value: Any, ttl: int) -> bool:
        """
        Store a value in cache with a TTL in seconds.
        Returns True on success, False on error.
        """
        try:
            serialized = json.dumps(value, default=str)
            await self._redis.set(key, serialized, ex=ttl)
            return True
        except Exception as exc:
            logger.warning("Cache SET failed for key=%s: %s", key, exc)
            return False

    async def delete(self, key: str) -> bool:
        """Delete a specific cache key."""
        try:
            await self._redis.delete(key)
            return True
        except Exception as exc:
            logger.warning("Cache DELETE failed for key=%s: %s", key, exc)
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a glob pattern.
        Use sparingly — SCAN is O(N) over the keyspace.
        Returns the count of deleted keys.
        """
        try:
            deleted = 0
            async for key in self._redis.scan_iter(match=pattern, count=100):
                await self._redis.delete(key)
                deleted += 1
            return deleted
        except Exception as exc:
            logger.warning("Cache DELETE_PATTERN failed for pattern=%s: %s", pattern, exc)
            return 0

    # ── Typed helpers for specific cache shapes ────────────────────────────────

    async def get_metrics_overview(
        self,
        project_id: str,
        window_minutes: int,
    ) -> dict | None:
        key = f"metrics:overview:{project_id}:{window_minutes}"
        return await self.get(key)

    async def set_metrics_overview(
        self,
        project_id: str,
        window_minutes: int,
        data: dict,
    ) -> None:
        key = f"metrics:overview:{project_id}:{window_minutes}"
        await self.set(key, data, METRICS_CACHE_TTL_SECONDS)

    async def get_service_metrics(
        self,
        service_id: str,
        window_minutes: int,
    ) -> dict | None:
        key = f"metrics:service:{service_id}:{window_minutes}"
        return await self.get(key)

    async def set_service_metrics(
        self,
        service_id: str,
        window_minutes: int,
        data: dict,
    ) -> None:
        key = f"metrics:service:{service_id}:{window_minutes}"
        await self.set(key, data, METRICS_CACHE_TTL_SECONDS)

    async def invalidate_service_metrics(self, service_id: str) -> None:
        """
        Invalidate all cached metrics for a service.
        Called after aggregation writes new data so the next request
        gets fresh numbers, not a stale cached response.
        """
        await self.delete_pattern(f"metrics:service:{service_id}:*")

    async def invalidate_project_overview(self, project_id: str) -> None:
        """Invalidate the project overview cache after any service updates."""
        await self.delete_pattern(f"metrics:overview:{project_id}:*")

    # ── Health snapshot ────────────────────────────────────────────────────────

    async def set_health_snapshot(
        self,
        service_id: str,
        snapshot: dict,
    ) -> None:
        """
        Write the latest health state for a service.
        Used by MetricAggregationService after each aggregation cycle.

        Key: health:{service_id}
        TTL: 60s — if the aggregation engine stops running, stale health
             data expires rather than being served indefinitely.
        """
        key = f"health:{service_id}"
        await self.set(key, snapshot, HEALTH_SNAPSHOT_TTL_SECONDS)

    async def get_health_snapshot(self, service_id: str) -> dict | None:
        """
        Read the cached health snapshot for a service.
        Returns None if the snapshot has expired or was never written.
        Callers fall back to a live DB query on None.
        """
        key = f"health:{service_id}"
        return await self.get(key)

    # ── Rate limiting ──────────────────────────────────────────────────────────

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> tuple[bool, int]:
        """
        Sliding-window rate limiter using Redis atomic INCR + EXPIRE.

        How it works:
          1. INCR a key named ratelimit:{identifier}:{current_minute}
          2. On first write, set TTL = window_seconds * 2 (auto-cleanup)
          3. If count > limit → reject

        Returns: (allowed: bool, current_count: int)

        Why INCR + EXPIRE (not a Lua script)?
          For V1, the 1-minute window is coarse enough that the tiny race
          between INCR and EXPIRE (both atomic individually but not together)
          is acceptable. A Lua script makes it atomic but adds complexity.
          At V2 scale, switch to a Redis Lua script or use a library like
          `fastapi-limiter` that handles this correctly.

        Why bucket by minute, not a true sliding window?
          True sliding windows require storing per-request timestamps in
          a sorted set (ZADD/ZRANGEBYSCORE). For V1's protection-level
          needs, per-minute buckets are simpler and sufficient.
        """
        import time
        minute_bucket = int(time.time() // window_seconds)
        key = f"ratelimit:{identifier}:{minute_bucket}"

        try:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds * 2)
            results = await pipe.execute()
            count = results[0]
            allowed = count <= limit
            return allowed, count
        except Exception as exc:
            # If Redis is unavailable, allow the request rather than blocking
            # all telemetry ingestion. Log the error and fail open.
            logger.warning(
                "Rate limit check failed for identifier=%s: %s — failing open",
                identifier, exc,
            )
            return True, 0
