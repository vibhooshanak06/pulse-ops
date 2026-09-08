"""
Auth schemas.

Pydantic models for request/response validation on auth endpoints.

Separation from ORM models is intentional:
  - ORM models define the database shape
  - Schemas define what the API accepts and returns
  - We never return password_hash to the client
  - We can add computed fields (e.g. has_organization) to responses
    without touching the DB model
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Request schemas ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    org_name: str = Field(min_length=1, max_length=255,
                          description="Name of the organization to create")

    @field_validator("password")
    @classmethod
    def password_not_common(cls, v: str) -> str:
        common = {"password", "password1", "12345678", "qwerty123"}
        if v.lower() in common:
            raise ValueError("Password is too common.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── Response schemas ──────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RegisterResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    message: str = "Account created successfully."
