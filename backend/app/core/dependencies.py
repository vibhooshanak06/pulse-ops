"""
FastAPI dependency injection.

These functions are injected into route handlers via Depends().
Centralizing them here means auth logic lives in one place —
changing how tokens are validated only requires editing this file.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.core.security import decode_access_token
from app.db.session import get_db

# HTTPBearer extracts the token from the Authorization: Bearer <token> header
bearer_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """
    Validate the JWT token and return the user's ID (subject claim).

    Raises HTTP 401 if the token is missing, expired, or invalid.
    Used in every protected route.
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


# Re-export get_db and get_redis here so routes only need to import
# from app.core.dependencies — one import location for all dependencies.
__all__ = ["get_current_user_id", "get_db", "get_redis"]
