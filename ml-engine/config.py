"""
ML Engine configuration.

The ml-engine is a separate Python process from the FastAPI backend.
It reads metric_aggregates from PostgreSQL and writes anomalies back.
It uses the SYNC database URL because its scheduler is synchronous.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    # ── PostgreSQL (sync — ml-engine uses synchronous SQLAlchemy) ────────────
    SYNC_DATABASE_URL: str

    # ── Anomaly detection tuning ──────────────────────────────────────────────
    # Z-score threshold: values beyond this many std deviations are anomalous
    ZSCORE_THRESHOLD: float = 3.0

    # Isolation Forest contamination: expected fraction of anomalies in data
    # 0.05 means we expect ~5% of data points to be anomalous
    ISOLATION_FOREST_CONTAMINATION: float = 0.05

    # Minimum data points needed before running detection
    MIN_DATA_POINTS: int = 10

    # How many historical minutes to use as the baseline window
    BASELINE_WINDOW_MINUTES: int = 60

    # How often the detection job runs (in minutes)
    DETECTION_INTERVAL_MINUTES: int = 1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


ml_settings = MLSettings()
