"""
Application configuration.

Pydantic Settings reads values from environment variables (and .env file).
Every config value is typed and validated at startup — if a required variable
is missing, the app fails immediately with a clear error instead of silently
using a wrong value at runtime.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_SECRET_KEY: str

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    DATABASE_URL: str          # async URL  → used by SQLAlchemy at runtime
    SYNC_DATABASE_URL: str     # sync URL   → used by Alembic for migrations

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── AI / LLM ──────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    TELEMETRY_RATE_LIMIT_PER_MINUTE: int = 1000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",   # silently ignore env vars not declared as fields
    )


# Single instance imported everywhere — never instantiate Settings() directly
# in other modules. Always import this `settings` object.
settings = Settings()
