"""
Model registry — import every model here.

WHY THIS FILE EXISTS:
  SQLAlchemy's declarative system registers models in Base.metadata only
  when the model's Python module is imported. Alembic reads Base.metadata
  to auto-generate migrations via --autogenerate.

  If a model file is never imported, Alembic never sees it, and the table
  is silently missing from the migration. This file is the single place
  that guarantees every model is imported before Alembic inspects metadata.

  alembic/env.py does:    import app.db.models  (this file)
  This one import pulls in all 13 models.

IMPORT ORDER:
  Order matters when forward references in TYPE_CHECKING blocks exist.
  We import in dependency order (no model references one that isn't
  imported yet):

  Layer 1 — no FK dependencies
    User, Organization

  Layer 2 — depends on Layer 1
    UserOrganization (→ User, Organization)
    Project          (→ Organization)

  Layer 3 — depends on Layer 2
    ApiKey   (→ Project)
    Service  (→ Project)

  Layer 4 — depends on Layer 3
    Endpoint         (→ Service)
    TelemetryEvent   (→ Service, Endpoint)
    MetricAggregate  (→ Service, Endpoint)
    Incident         (→ Project, Service)

  Layer 5 — depends on Layer 4
    Anomaly          (→ Service, Endpoint, MetricAggregate, Incident)
    IncidentEvidence (→ Incident)
    AiExplanation    (→ Incident)
"""

# Layer 1
from app.db.models.user import User
from app.db.models.organization import Organization

# Layer 2
from app.db.models.user_organization import UserOrganization
from app.db.models.project import Project

# Layer 3
from app.db.models.api_key import ApiKey
from app.db.models.service import Service

# Layer 4
from app.db.models.endpoint import Endpoint
from app.db.models.telemetry_event import TelemetryEvent
from app.db.models.metric_aggregate import MetricAggregate
from app.db.models.incident import Incident

# Layer 5
from app.db.models.anomaly import Anomaly
from app.db.models.incident_evidence import IncidentEvidence
from app.db.models.ai_explanation import AiExplanation

# Public API — everything a service or repository layer needs to import
__all__ = [
    "User",
    "Organization",
    "UserOrganization",
    "Project",
    "ApiKey",
    "Service",
    "Endpoint",
    "TelemetryEvent",
    "MetricAggregate",
    "Incident",
    "Anomaly",
    "IncidentEvidence",
    "AiExplanation",
]
