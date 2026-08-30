"""
API v1 router.

All route modules are included here with their prefixes and tags.
This keeps main.py clean — it only mounts this single router.
As we add phases, we uncomment the relevant route imports.
"""

from fastapi import APIRouter

# Routes will be imported and included here as each phase is built.
# Placeholder imports are commented out until those phases are complete.

# from app.api.v1.routes import auth
# from app.api.v1.routes import services
# from app.api.v1.routes import telemetry
# from app.api.v1.routes import metrics
# from app.api.v1.routes import anomalies
# from app.api.v1.routes import incidents
# from app.api.v1.routes import api_keys

api_router = APIRouter()

# router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# router.include_router(services.router, prefix="/services", tags=["Services"])
# router.include_router(telemetry.router, prefix="/telemetry", tags=["Telemetry"])
# router.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
# router.include_router(anomalies.router, prefix="/anomalies", tags=["Anomalies"])
# router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
# router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])
