"""
Service schemas.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class ServiceResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    health_status: str
    created_at: datetime
    last_seen_at: datetime | None

    model_config = {"from_attributes": True}


class ServiceListResponse(BaseModel):
    items: list[ServiceResponse]
    total: int
