"""
Statistical anomaly detection — z-score based.

Z-score formula:
  z = (current_value - baseline_mean) / baseline_std

A z-score tells you "how many standard deviations from normal is this value?"

  z = 2.0  →  two standard deviations above mean → unusual but not alarming
  z = 3.0  →  three standard deviations → anomalous (0.3% probability if normal)
  z = 5.0  →  five standard deviations → very likely a real problem

Threshold: ZSCORE_THRESHOLD = 3.0 (configurable)
  Below threshold → normal
  Above threshold → anomalous, score proportional to how far above threshold

Score normalization:
  We convert z-scores to a 0.0-1.0 scale for the combined scorer.
  Uses a sigmoid-like mapping:
    score = min(1.0, (z - threshold) / threshold)
  So:
    z = 3.0 → score = 0.0  (just at threshold)
    z = 6.0 → score = 1.0  (twice threshold — very anomalous)

Direction matters:
  - latency:    high is bad (z > threshold = anomaly)
  - error_rate: high is bad (z > threshold = anomaly)
  - throughput: BOTH directions are anomalous:
                  sudden spike → traffic anomaly
                  sudden drop  → service degradation / routing failure

Per-metric detection returns a StatisticalAnomaly with:
  - is_anomalous: bool
  - z_score:      float (raw z value for logging/debugging)
  - score:        float 0.0-1.0 (normalized for combined scorer)
  - metric_type:  str
  - baseline_value: float (what normal looked like)
  - current_value:  float (what we observed)
  - deviation_percent: float (% change from baseline)
"""

from dataclasses import dataclass

from app.services.anomaly_detection.baseline import BaselineStats

# Default z-score threshold; overridden by settings in the full service
DEFAULT_ZSCORE_THRESHOLD = 3.0


@dataclass
class StatisticalAnomaly:
    is_anomalous:       bool
    z_score:            float
    score:              float          # 0.0 – 1.0
    metric_type:        str
    baseline_value:     float
    current_value:      float
    deviation_percent:  float


def _zscore_to_score(z: float, threshold: float) -> float:
    """Convert a raw z-score to a normalized 0.0-1.0 anomaly score."""
    if z <= threshold:
        return 0.0
    return min(1.0, (z - threshold) / threshold)


def _deviation_percent(baseline: float, current: float) -> float:
    """Percentage change from baseline to current, signed."""
    if baseline == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - baseline) / abs(baseline)) * 100, 2)


def detect_latency_anomaly(
    baseline: BaselineStats,
    current_p95: float,
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> StatisticalAnomaly:
    """
    Detect latency anomaly on P95 latency.
    Only high latency is anomalous (low latency is never a problem).
    """
    mean, std = baseline.mean, baseline.std

    if std == 0:
        # Zero std means all historical values were identical.
        # Use a small epsilon to avoid division by zero.
        std = max(mean * 0.01, 0.1)

    z = (current_p95 - mean) / std
    is_anomalous = z > threshold

    return StatisticalAnomaly(
        is_anomalous      = is_anomalous,
        z_score           = round(z, 3),
        score             = _zscore_to_score(z, threshold) if z > 0 else 0.0,
        metric_type       = "latency",
        baseline_value    = round(mean, 2),
        current_value     = round(current_p95, 2),
        deviation_percent = _deviation_percent(mean, current_p95),
    )


def detect_error_rate_anomaly(
    baseline: BaselineStats,
    current_error_rate: float,
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> StatisticalAnomaly:
    """
    Detect error rate anomaly.
    Only high error rates are anomalous.

    Edge case: if baseline error rate is near zero (very healthy service),
    even a small absolute increase can be significant. We apply a floor
    on the std to ensure we catch these cases.
    """
    mean, std = baseline.mean, baseline.std

    # Floor: std should be at least 0.002 (0.2%) for error rate.
    # Prevents over-sensitivity when baseline is perfectly clean (std=0).
    std = max(std, 0.002)

    z = (current_error_rate - mean) / std
    is_anomalous = z > threshold

    return StatisticalAnomaly(
        is_anomalous      = is_anomalous,
        z_score           = round(z, 3),
        score             = _zscore_to_score(z, threshold) if z > 0 else 0.0,
        metric_type       = "error_rate",
        baseline_value    = round(mean, 6),
        current_value     = round(current_error_rate, 6),
        deviation_percent = _deviation_percent(mean, current_error_rate),
    )


def detect_throughput_anomaly(
    baseline: BaselineStats,
    current_throughput: float,
    threshold: float = DEFAULT_ZSCORE_THRESHOLD,
) -> StatisticalAnomaly:
    """
    Detect throughput anomaly — both spikes and drops are anomalous.
    Uses abs(z) so both directions trigger at the same threshold.
    """
    mean, std = baseline.mean, baseline.std
    std = max(std, mean * 0.05, 0.1)   # floor at 5% of mean

    z     = (current_throughput - mean) / std
    abs_z = abs(z)
    is_anomalous = abs_z > threshold

    return StatisticalAnomaly(
        is_anomalous      = is_anomalous,
        z_score           = round(z, 3),
        score             = _zscore_to_score(abs_z, threshold),
        metric_type       = "throughput",
        baseline_value    = round(mean, 2),
        current_value     = round(current_throughput, 2),
        deviation_percent = _deviation_percent(mean, current_throughput),
    )
