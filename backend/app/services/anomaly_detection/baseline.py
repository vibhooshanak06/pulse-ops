"""
Baseline calculator.

Computes "normal" behavior for a service metric by looking at
historical metric_aggregates over a configurable look-back window.

Design decisions:

WHY USE metric_aggregates INSTEAD OF raw telemetry_events:
  Aggregates are pre-computed, indexed, and compact.
  A 24-hour baseline at 1-min granularity = 1440 rows.
  Reading 1440 small aggregate rows is fast; reading thousands of raw
  events for the same period would be much slower.

BASELINE WINDOW:
  Default: 60 minutes of history (60 aggregate windows × 1 min each).
  This is short enough to adapt to daily traffic patterns (morning vs
  evening traffic shapes differ) while long enough to smooth out noise.
  In V2 this becomes configurable per-service.

MINIMUM POINTS:
  We require at least MIN_BASELINE_POINTS data points before computing
  a baseline. If a service is new, we return a "no baseline" signal
  and skip anomaly detection for that cycle — better than false positives
  from meaningless statistics on 2 data points.

WHAT WE CALCULATE:
  For each metric type we compute:
    mean  → the expected "normal" value
    std   → how much it normally varies
  These feed directly into the z-score calculation in statistical.py.
"""

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np

# Minimum number of data points required to compute a meaningful baseline.
# Below this threshold, detection is skipped to avoid false positives.
MIN_BASELINE_POINTS = 10


@dataclass
class BaselineStats:
    """
    Computed baseline statistics for one metric of one service.
    All values are floats; std=0 means we only have one data point.
    """
    mean:        float
    std:         float
    min_val:     float
    max_val:     float
    sample_size: int
    metric_type: str    # "latency" | "error_rate" | "throughput" | "request_count"


class ServiceBaseline(NamedTuple):
    """Full baseline for a service — one BaselineStats per tracked metric."""
    p95_latency:    BaselineStats | None
    error_rate:     BaselineStats | None
    throughput_rpm: BaselineStats | None
    request_count:  BaselineStats | None
    has_baseline:   bool     # False if not enough data


def compute_baseline(aggregate_windows: list) -> ServiceBaseline:
    """
    Compute baseline statistics from a list of MetricAggregate ORM objects
    (or any objects with the same attribute names).

    Called with the historical window EXCLUDING the current window being
    evaluated — we never include the anomalous window in its own baseline.

    Returns ServiceBaseline with has_baseline=False if insufficient data.
    """
    if len(aggregate_windows) < MIN_BASELINE_POINTS:
        return ServiceBaseline(
            p95_latency=None, error_rate=None,
            throughput_rpm=None, request_count=None,
            has_baseline=False,
        )

    def _stats(values: list[float], metric_type: str) -> BaselineStats:
        arr = np.array(values, dtype=np.float64)
        return BaselineStats(
            mean        = float(np.mean(arr)),
            std         = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            min_val     = float(np.min(arr)),
            max_val     = float(np.max(arr)),
            sample_size = len(arr),
            metric_type = metric_type,
        )

    return ServiceBaseline(
        p95_latency    = _stats([w.p95_latency_ms  for w in aggregate_windows], "latency"),
        error_rate     = _stats([w.error_rate       for w in aggregate_windows], "error_rate"),
        throughput_rpm = _stats([w.throughput_rpm   for w in aggregate_windows], "throughput"),
        request_count  = _stats([w.request_count    for w in aggregate_windows], "request_count"),
        has_baseline   = True,
    )
