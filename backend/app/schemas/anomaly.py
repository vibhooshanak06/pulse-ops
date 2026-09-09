"""
Anomaly response schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AnomalyResponse(BaseModel):
    id:                UUID
    service_id:        UUID
    endpoint_id:       UUID | None
    metric_type:       str
    severity:          str
    combined_score:    float
    statistical_score: float
    ml_score:          float
    baseline_value:    float
    current_value:     float
    deviation_percent: float
    detected_at:       datetime
    resolved_at:       datetime | None
    incident_id:       UUID | None

    model_config = {"from_attributes": True}


class AnomalyListResponse(BaseModel):
    items:  list[AnomalyResponse]
    total:  int
    active: int   # count where resolved_at is None
