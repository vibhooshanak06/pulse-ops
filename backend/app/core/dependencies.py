"""
FastAPI dependency injection.

get_current_user_id  → returns raw str UUID from JWT (lightweight, no DB hit)
get_current_user     → returns full User ORM object (DB hit, used by most routes)

Why two variants?
  Some operations (e.g. rate-limit checks) only need the user ID, not the full
  object. get_current_user_id avoids the DB round-trip in those cases.
  Most routes use get_current_user which loads the User and confirms the account
  is still active — essential after a password reset or account suspension.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """Validate JWT and return the subject claim (user UUID as string)."""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate JWT and load the full User from the database.

    Raises HTTP 401 if:
      - The token is invalid or expired (caught by get_current_user_id)
      - The user no longer exists
      - The account has been deactivated
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
        )

    user = await UserRepository(db).get_by_id(uid)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


__all__ = ["get_current_user_id", "get_current_user", "get_db", "get_redis"]
