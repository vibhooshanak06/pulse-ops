"""
Alembic environment configuration.

Key decisions:
- We use the SYNC_DATABASE_URL (psycopg2) for Alembic because Alembic's
  migration runner is synchronous. The async engine is only for FastAPI.
- We import Base from app.db.base so Alembic can auto-detect all models
  for --autogenerate. Every model file must be imported somewhere in
  app.db.models.__init__ to be visible here.
- The URL comes from our Settings object, never hardcoded.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the backend directory to sys.path so app imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.base import Base

# Import all models so Alembic can see them for autogenerate.
# We will populate this as we create models in Phase 2.
import app.db.models  # noqa: F401

config = context.config

# Override sqlalchemy.url with the sync URL from our settings
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,      # detect column type changes
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
