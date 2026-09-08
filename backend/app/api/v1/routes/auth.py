"""
Auth routes.

POST /v1/auth/register  → create user + org + JWT
POST /v1/auth/login     → verify credentials + JWT
GET  /v1/auth/me        → return current user profile

The login endpoint accepts application/x-www-form-urlencoded
in addition to JSON so it's compatible with the Swagger UI
"Authorize" button (which uses form data).
"""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
    summary="Register a new user",
    description=(
        "Creates a user account and a new organization in one step. "
        "Returns a JWT access token so the client is immediately authenticated."
    ),
)
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    return await AuthService(db).register(req)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await AuthService(db).login(req)


@router.post(
    "/login/form",
    response_model=TokenResponse,
    summary="Login via form data (Swagger UI compatible)",
    include_in_schema=True,
)
async def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Accepts OAuth2 form fields (username + password).
    The Swagger UI "Authorize" button posts to this endpoint.
    `username` field is treated as email.
    """
    req = LoginRequest(email=form.username, password=form.password)
    return await AuthService(db).login(req)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)
