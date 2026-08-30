"""
SDK configuration.

Applications configure the SDK by passing these values to the middleware.
No .env file needed here — the consuming application provides these values
from its own environment.
"""

from dataclasses import dataclass, field


@dataclass
class PulseOpsConfig:
    """
    Configuration for the PulseOps telemetry middleware.

    Required:
        api_key:      The project API key generated in PulseOps dashboard.
        service_name: Identifies which service this telemetry belongs to.
        ingestion_url: The PulseOps backend telemetry endpoint.

    Optional:
        batch_size:   Number of events to accumulate before flushing.
                      Lower = more real-time, higher = more efficient.
        flush_interval_seconds: Max seconds between flushes even if
                      batch_size hasn't been reached.
        timeout_seconds: HTTP timeout for each telemetry POST.
        excluded_paths: Paths the middleware should NOT instrument.
                      Health checks and metrics endpoints are good candidates.
    """
    api_key: str
    service_name: str
    ingestion_url: str = "http://localhost:8000/v1/telemetry"

    batch_size: int = 10
    flush_interval_seconds: int = 5
    timeout_seconds: int = 5

    excluded_paths: list[str] = field(default_factory=lambda: [
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    ])
