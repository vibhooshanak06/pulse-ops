"""
Combined anomaly scorer.

Merges statistical (z-score) and ML (Isolation Forest) signals into a
single anomaly score and maps it to a human-readable severity level.

WEIGHTING RATIONALE:
  statistical_weight = 0.55   ML_weight = 0.45

  We weight statistical slightly higher because:
    - Z-score is directly interpretable (we can cite exact values)
    - It's faster to compute and easier to explain in an incident report
    - Isolation Forest is newer and less battle-tested per signal type

  These weights are V1 defaults. In V2 they become configurable per-project
  and can be tuned based on false-positive feedback.

SEVERITY MAPPING:
  0.00 – 0.30 → LOW       (unusual but not urgent)
  0.30 – 0.60 → MEDIUM    (investigate soon)
  0.60 – 0.80 → HIGH      (investigate now)
  0.80 – 1.00 → CRITICAL  (all hands on deck)

MULTI-SIGNAL COMBINATION:
  If multiple statistical detectors fire (latency + error_rate), we take
  the MAX statistical score rather than averaging. This prevents a severe
  latency anomaly from being diluted by a normal error_rate.

  combined_score = max(stat_scores) * stat_weight + if_score * ml_weight

  Rationale: the system is only as healthy as its worst metric.
  If P95 latency is critical but error rate is fine, the combined score
  should reflect the latency severity, not an average.
"""

from dataclasses import dataclass

from app.services.anomaly_detection.isolation_forest import IsolationForestResult
from app.services.anomaly_detection.statistical import StatisticalAnomaly

# Scoring weights — must sum to 1.0
STATISTICAL_WEIGHT = 0.55
ML_WEIGHT          = 0.45

# Severity thresholds
SEVERITY_THRESHOLDS = {
    "CRITICAL": 0.80,
    "HIGH":     0.60,
    "MEDIUM":   0.30,
    "LOW":      0.0,
}


@dataclass
class CombinedAnomalyScore:
    """Final output of the anomaly detection pipeline for one window."""
    combined_score:       float   # 0.0 – 1.0
    statistical_score:    float   # max of individual stat scores
    ml_score:             float   # isolation forest score
    severity:             str     # LOW / MEDIUM / HIGH / CRITICAL
    is_anomalous:         bool    # True if any signal detected an anomaly
    triggered_metrics:    list[str]  # which metrics fired
    # Most significant anomaly details (for evidence collection)
    primary_metric_type:  str | None
    baseline_value:       float
    current_value:        float
    deviation_percent:    float


def _score_to_severity(score: float) -> str:
    """Map a 0.0-1.0 score to a severity string."""
    if score >= SEVERITY_THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    if score >= SEVERITY_THRESHOLDS["HIGH"]:
        return "HIGH"
    if score >= SEVERITY_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def compute_combined_score(
    statistical_results: list[StatisticalAnomaly],
    if_result: IsolationForestResult,
) -> CombinedAnomalyScore:
    """
    Combine all detection signals into one CombinedAnomalyScore.

    statistical_results: list of StatisticalAnomaly from latency, error_rate,
                         throughput detectors (some may not be anomalous)
    if_result:           IsolationForestResult from the ML detector
    """
    # Extract scores from statistical detectors
    anomalous_stats = [s for s in statistical_results if s.is_anomalous]
    all_stat_scores = [s.score for s in statistical_results]

    # Take the MAX statistical score (worst single-metric condition)
    max_stat_score = max(all_stat_scores) if all_stat_scores else 0.0

    # Combined score: weighted merge
    combined = (max_stat_score * STATISTICAL_WEIGHT) + (if_result.score * ML_WEIGHT)
    combined = round(min(1.0, combined), 4)

    # Determine which metrics triggered
    triggered = [s.metric_type for s in anomalous_stats]
    if if_result.is_anomalous and not triggered:
        triggered.append("multi_metric")   # IF fired but no individual metric did

    # Find the most significant statistical anomaly for evidence
    primary = max(anomalous_stats, key=lambda s: s.score) if anomalous_stats else None

    is_anomalous = bool(anomalous_stats) or if_result.is_anomalous

    return CombinedAnomalyScore(
        combined_score      = combined,
        statistical_score   = round(max_stat_score, 4),
        ml_score            = if_result.score,
        severity            = _score_to_severity(combined),
        is_anomalous        = is_anomalous,
        triggered_metrics   = triggered,
        primary_metric_type = primary.metric_type if primary else None,
        baseline_value      = primary.baseline_value if primary else 0.0,
        current_value       = primary.current_value  if primary else 0.0,
        deviation_percent   = primary.deviation_percent if primary else 0.0,
    )
