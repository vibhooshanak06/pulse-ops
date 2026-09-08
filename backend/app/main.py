"""
PulseOps AI — FastAPI application entry point.

Startup lifecycle:
  1. Connect to Redis (verify ping)
  2. (Database connections are managed per-request via get_db dependency)

Shutdown lifecycle:
  1. Close Redis connection pool

The lifespan context manager is the modern FastAPI way to handle
startup/shutdown — it replaces the deprecated @app.on_event decorators.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.redis_client import close_redis, init_redis

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown of shared resources."""
    # ── Startup ──
    logger.info("Starting PulseOps AI backend...")
    logger.info(f"Environment: {settings.APP_ENV}")

    logger.info("Connecting to Redis...")
    try:
        await init_redis()
        logger.info("Redis connected.")
    except Exception as exc:
        # Redis is required for caching and rate limiting (Phase 8) but
        # the app can start without it in development — auth and telemetry
        # ingestion work without a cache hit. Log a clear warning so the
        # developer knows Redis is unavailable.
        logger.warning(
            f"Redis unavailable: {exc}. "
            "Caching and rate limiting will be disabled until Redis is reachable. "
            "Install Redis to enable Phase 8 features."
        )

    logger.info("PulseOps AI backend ready.")

    yield  # Application runs here

    # ── Shutdown ──
    logger.info("Shutting down PulseOps AI backend...")
    await close_redis()
    logger.info("Redis connection closed.")
    logger.info("Shutdown complete.")


# ── FastAPI application ────────────────────────────────────────────────────────
app = FastAPI(
    title="PulseOps AI",
    description=(
        "AI-Powered API Observability & Incident Intelligence Platform. "
        "Collects API telemetry, detects anomalies, correlates incidents, "
        "and generates evidence-grounded AI explanations."
    ),
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc UI
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# In development we allow the Vite dev server (port 5173).
# In production this should be locked to the actual frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # alternate dev port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount API router ──────────────────────────────────────────────────────────
app.include_router(api_router, prefix="/v1")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Simple health check endpoint.
    Returns 200 if the application is running.
    Used by load balancers and monitoring tools.
    """
    return {
        "status": "healthy",
        "service": "pulseops-backend",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
    }
