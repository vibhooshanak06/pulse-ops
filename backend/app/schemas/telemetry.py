"""
Telemetry ingestion schemas.

TelemetryEventIn   → one event from the SDK (per request captured)
TelemetryBatchRequest → the full batch payload the SDK POSTs
TelemetryBatchResponse → what we return to the SDK (minimal, fast)

Validation rules:
  - latency_ms must be >= 0 (negative latency is impossible)
  - latency_ms cap at 300_000ms (5 min) — anything higher is a bug in the SDK clock
  - status_code must be a valid HTTP range (100-599)
  - method is uppercased on ingest
  - endpoint path is stripped and truncated to 1000 chars
  - timestamp must be timezone-aware; if naive, we reject it — ambiguous timestamps
    corrupt time-window metrics

Batch size:
  Max 500 events per batch. The SDK sends batches of 10 by default.
  500 is a hard cap to prevent a single malformed client from writing
  50MB of garbage into the database in one request.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class TelemetryEventIn(BaseModel):
    endpoint: Annotated[str, Field(min_length=1, max_length=1000)]
    method: Annotated[str, Field(min_length=1, max_length=10)]
    status_code: Annotated[int, Field(ge=100, le=599)]
    latency_ms: Annotated[float, Field(ge=0.0, le=300_000.0)]
    timestamp: datetime

    @field_validator("method")
    @classmethod
    def uppercase_method(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("endpoint")
    @classmethod
    def normalize_endpoint(cls, v: str) -> str:
        # Strip whitespace, ensure leading slash
        v = v.strip()
        if not v.startswith("/"):
            v = "/" + v
        return v[:1000]

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware (include UTC offset or 'Z'). "
                "Naive timestamps are ambiguous and corrupt time-window metrics."
            )
        return v

    @field_validator("latency_ms")
    @classmethod
    def round_latency(cls, v: float) -> float:
        return round(v, 2)


class TelemetryBatchRequest(BaseModel):
    service_name: Annotated[str, Field(min_length=1, max_length=255)]
    events: Annotated[
        list[TelemetryEventIn],
        Field(min_length=1, max_length=500),
    ]

    @field_validator("service_name")
    @classmethod
    def normalize_service_name(cls, v: str) -> str:
        return v.strip()


class TelemetryBatchResponse(BaseModel):
    accepted: int       # number of events stored
    rejected: int       # number of events that failed validation (should be 0 if Pydantic ran)
    service_id: str     # UUID of the resolved/created service
    message: str = "Telemetry received."
