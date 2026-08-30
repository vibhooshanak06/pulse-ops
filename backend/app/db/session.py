"""
Database session factory.

We use an async engine (asyncpg driver) so FastAPI's async route handlers
never block the event loop on database I/O.

AsyncSessionLocal is a session factory — call it to get a session.
get_db() is a FastAPI dependency that yields one session per request,
then commits or rolls back and closes automatically.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# create_async_engine creates a connection pool.
# pool_pre_ping=True: verifies connections are alive before using them,
# which prevents errors after the database restarts.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,   # logs SQL queries in development
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # prevents lazy-load errors after commit
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency. Usage:

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
