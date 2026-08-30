"""
Demo service configuration.

Reads SDK connection settings and failure simulation flags from environment.
Failure simulation flags (SIMULATE_LATENCY, SIMULATE_ERRORS, etc.) are used
in Phase 15 to trigger controlled degradation scenarios.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DemoSettings(BaseSettings):
    APP_ENV: str = "development"

    # PulseOps SDK settings
    PULSEOPS_API_KEY: str
    PULSEOPS_SERVICE_NAME: str = "demo-service"
    PULSEOPS_INGESTION_URL: str = "http://localhost:8000/v1/telemetry"

    # Failure simulation — Phase 15
    SIMULATE_LATENCY: bool = False
    SIMULATE_ERRORS: bool = False
    LATENCY_SPIKE_MS: int = 2000
    ERROR_RATE_PERCENT: int = 0    # 0–100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


demo_settings = DemoSettings()
