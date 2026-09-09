"""
API v1 router.

URL hierarchy mirrors the ownership model:
  /auth/*
  /organizations/*
  /organizations/{org_id}/projects/*
  /organizations/{org_id}/projects/{project_id}/services/*
  /organizations/{org_id}/projects/{project_id}/api-keys/*
  /organizations/{org_id}/projects/{project_id}/metrics/*   ← Phase 7
  /telemetry                                                 ← flat, API-key auth
"""

from fastapi import APIRouter

from app.api.v1.routes import (
    auth, organizations, projects, services,
    api_keys, telemetry, metrics, anomalies,
)

api_router = APIRouter()

# ── Auth ──────────────────────────────────────────────────────────────────────
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

# ── Organizations ─────────────────────────────────────────────────────────────
api_router.include_router(
    organizations.router,
    prefix="/organizations",
    tags=["Organizations"],
)

# ── Projects (nested under org) ───────────────────────────────────────────────
api_router.include_router(
    projects.router,
    prefix="/organizations/{org_id}/projects",
    tags=["Projects"],
)

# ── Services (nested under project) ───────────────────────────────────────────
api_router.include_router(
    services.router,
    prefix="/organizations/{org_id}/projects/{project_id}/services",
    tags=["Services"],
)

# ── API Keys (nested under project) ───────────────────────────────────────────
api_router.include_router(
    api_keys.router,
    prefix="/organizations/{org_id}/projects/{project_id}/api-keys",
    tags=["API Keys"],
)

# ── Metrics (nested under project) ────────────────────────────────────────────
# One router handles both:
#   /metrics/overview                       → project-level summary
#   /metrics/services/{id}/metrics          → service detail
#   /metrics/services/{id}/health           → health snapshot
api_router.include_router(
    metrics.router,
    prefix="/organizations/{org_id}/projects/{project_id}/metrics",
    tags=["Metrics"],
)

# ── Telemetry ingestion (flat, API-key auth) ───────────────────────────────────
api_router.include_router(
    telemetry.router,
    prefix="/telemetry",
    tags=["Telemetry"],
)

# ── Anomalies (nested under project) ──────────────────────────────────────────
api_router.include_router(
    anomalies.router,
    prefix="/organizations/{org_id}/projects/{project_id}/anomalies",
    tags=["Anomalies"],
)
