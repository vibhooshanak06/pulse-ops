"""
API key schemas.

ApiKeyCreatedResponse is the only place the plain-text key appears.
After this response is sent, the key cannot be recovered — only revoked.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Human-readable label, e.g. 'Payment Service Production'",
    )


class ApiKeyResponse(BaseModel):
    """Safe to return at any time — never includes the raw key."""
    id: UUID
    project_id: UUID
    name: str
    key_prefix: str      # e.g. "po_live_ab" — safe to display
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(BaseModel):
    """
    Returned ONCE when the key is first created.
    Includes the full plain-text key — never returned again after this.
    The client must store it immediately.
    """
    key: str = Field(
        description=(
            "Full API key — store this now. "
            "It cannot be retrieved after this response."
        )
    )
    api_key: ApiKeyResponse
    message: str = (
        "API key created. Copy it now — it will not be shown again."
    )


class ApiKeyListResponse(BaseModel):
    items: list[ApiKeyResponse]
    total: int
