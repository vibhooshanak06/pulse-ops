"""
Metrics response schemas.

Three response shapes:

1. ServiceMetricsResponse  — full time-series for one service (service detail page)
   Contains: current snapshot + array of window aggregates for charts

2. OverviewResponse        — summary across all services in a project (dashboard home)
   Contains: service counts by health + active incident count + project-level aggregates

3. ServiceHealthResponse   — lightweight health snapshot (sidebar health indicators)
   Contains: just the current metrics snapshot + health status

Design note on "current" snapshot:
  Rather than returning the most recent single aggregate window (which might be
  incomplete if we're mid-minute), we compute a rolling window over the last
  N minutes and present that as "current". This gives a stable, representative
  view of current behavior rather than a fluctuating single-minute slice.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MetricWindow(BaseModel):
    """One time-window's worth of metrics — used as chart data points."""
    window_start:    datetime
    window_end:      datetime
    request_count:   int
    error_count:     int
    error_rate:      float
    throughput_rpm:  float
    avg_latency_ms:  float
    min_latency_ms:  float
    max_latency_ms:  float
    p50_latency_ms:  float
    p95_latency_ms:  float
    p99_latency_ms:  float

    model_config = {"from_attributes": True}


class CurrentMetricsSnapshot(BaseModel):
    """
    Rolling-window summary of current service behavior.
    Used as the "current" values on the service detail and health pages.
    """
    avg_latency_ms:  float
    p50_latency_ms:  float
    p95_latency_ms:  float
    p99_latency_ms:  float
    error_rate:      float
    request_count:   int
    throughput_rpm:  float
    health_status:   str
    window_minutes:  int     # how many minutes this snapshot covers


class EndpointMetricRow(BaseModel):
    """Per-endpoint performance summary — used in the endpoint table."""
    endpoint_id:    UUID
    path:           str
    method:         str
    request_count:  int
    avg_latency_ms: float
    p95_latency_ms: float
    error_rate:     float
    throughput_rpm: float


class ServiceMetricsResponse(BaseModel):
    """Full metrics response for one service — service detail page."""
    service_id:    UUID
    service_name:  str
    health_status: str
    current:       CurrentMetricsSnapshot
    time_series:   list[MetricWindow]    # chronological, for charts
    endpoints:     list[EndpointMetricRow]


class ServiceSummary(BaseModel):
    """Compact service summary for the overview dashboard."""
    service_id:    UUID
    service_name:  str
    health_status: str
    p95_latency_ms: float
    error_rate:    float
    request_count: int
    last_seen_at:  datetime | None


class OverviewResponse(BaseModel):
    """Overview dashboard response — summary across all project services."""
    total_services:    int
    healthy_services:  int
    degraded_services: int
    critical_services: int
    unknown_services:  int
    active_incidents:  int
    services:          list[ServiceSummary]
    # Aggregated project-level time series (sum across all services)
    time_series:       list[MetricWindow]


class ServiceHealthResponse(BaseModel):
    """Lightweight health snapshot — used by sidebar and service list."""
    service_id:    UUID
    service_name:  str
    health_status: str
    current:       CurrentMetricsSnapshot
