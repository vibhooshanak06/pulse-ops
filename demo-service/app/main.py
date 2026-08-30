"""
Demo Service — FastAPI application.

This is a realistic sample API that has the PulseOps SDK installed.
It demonstrates how any FastAPI application integrates PulseOps:
  1. Import PulseOpsMiddleware and PulseOpsConfig from the SDK.
  2. Add the middleware with your API key and service name.
  3. Every request is automatically instrumented — no changes to routes needed.

In Phase 15, the simulator will be enabled to generate realistic
failure scenarios that flow through the full PulseOps pipeline.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import demo_settings
from app.routes import orders, payment, products

# Import the PulseOps SDK
# This package is installed via: pip install -e ../../sdk
from pulseops_sdk import PulseOpsConfig, PulseOpsMiddleware

logging.basicConfig(
    level=logging.DEBUG if demo_settings.APP_ENV == "development" else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(f"Demo service starting | service={demo_settings.PULSEOPS_SERVICE_NAME}")
    logger.info(f"Telemetry target: {demo_settings.PULSEOPS_INGESTION_URL}")
    yield
    logger.info("Demo service shutting down.")


app = FastAPI(
    title="PulseOps Demo Service",
    description=(
        "Sample API that sends telemetry to PulseOps AI. "
        "Used for end-to-end demonstrations and failure simulation."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── PulseOps SDK Middleware ────────────────────────────────────────────────────
# This single line is all an application developer needs to add.
# The middleware automatically captures telemetry for every request.
app.add_middleware(
    PulseOpsMiddleware,
    config=PulseOpsConfig(
        api_key=demo_settings.PULSEOPS_API_KEY,
        service_name=demo_settings.PULSEOPS_SERVICE_NAME,
        ingestion_url=demo_settings.PULSEOPS_INGESTION_URL,
    ),
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(orders.router,   prefix="/api/orders",   tags=["Orders"])
app.include_router(payment.router,  prefix="/api/payment",  tags=["Payment"])


@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {
        "status": "healthy",
        "service": demo_settings.PULSEOPS_SERVICE_NAME,
        "telemetry_target": demo_settings.PULSEOPS_INGESTION_URL,
    }
