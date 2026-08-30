"""
Redis client.

We use a single redis.asyncio.Redis instance with a connection pool.
decode_responses=True means we always get strings back, not bytes —
this keeps cache key/value handling simple throughout the codebase.

The client is initialized once at startup (see main.py lifespan) and
shared across all requests via the module-level `redis_client` variable.
"""

import redis.asyncio as aioredis

from app.core.config import settings

redis_client: aioredis.Redis | None = None


def get_redis_url() -> str:
    """Build the Redis connection URL from settings."""
    if settings.REDIS_PASSWORD:
        return (
            f"redis://:{settings.REDIS_PASSWORD}@"
            f"{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        )
    return f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"


async def init_redis() -> aioredis.Redis:
    """
    Create the Redis connection pool and store it in the module-level variable.
    Called once during app startup.
    """
    global redis_client
    redis_client = aioredis.from_url(
        get_redis_url(),
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Verify connection is healthy
    await redis_client.ping()
    return redis_client


async def close_redis() -> None:
    """Close the Redis connection pool. Called during app shutdown."""
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None


def get_redis() -> aioredis.Redis:
    """
    FastAPI dependency. Usage:

        @router.get("/example")
        async def example(redis: Redis = Depends(get_redis)):
            ...
    """
    if redis_client is None:
        raise RuntimeError("Redis client not initialized. Check app startup.")
    return redis_client
