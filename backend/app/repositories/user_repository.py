"""
User repository — all database queries for the User model.

Repositories contain ONLY SQLAlchemy queries, no business logic.
The service layer decides what to do; the repository decides how to fetch it.

All methods are async because the FastAPI route handlers are async and
we use an async SQLAlchemy engine (asyncpg). Mixing sync and async DB
calls would block the event loop.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Used on login to find the user before verifying password."""
        result = await self._db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Fast existence check — avoids loading full User object."""
        result = await self._db.execute(
            select(User.id).where(User.email == email.lower())
        )
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        email: str,
        full_name: str,
        password_hash: str,
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            email=email.lower(),
            full_name=full_name,
            password_hash=password_hash,
            is_active=True,
            is_verified=False,
        )
        self._db.add(user)
        await self._db.flush()   # assigns DB-generated fields without committing
        return user
