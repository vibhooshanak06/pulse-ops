"""
Isolation Forest anomaly detection.

WHY ISOLATION FOREST:
  Z-score detects single-metric anomalies in isolation.
  Isolation Forest detects anomalies based on COMBINATIONS of metrics.

  Example z-score misses:
    latency:    z = 2.5  (below threshold, not flagged individually)
    error_rate: z = 2.5  (below threshold, not flagged individually)
    throughput: z = 2.5  (below threshold, not flagged individually)

  Combined: this pattern (latency + errors + traffic all slightly elevated)
  is very abnormal — Isolation Forest catches it because it's learned that
  these three values being simultaneously high has never occurred in normal data.

HOW ISOLATION FOREST WORKS (interview explanation):
  The algorithm randomly partitions the feature space by selecting a random
  feature and a random split value. Anomalous points are isolated in fewer
  splits because they're rare and far from dense clusters of normal data.
  The anomaly score is based on the average path length to isolate a point:
    short path → anomalous
    long path  → normal

FEATURE VECTOR:
  We use 5 features per window:
    [avg_latency_ms, p95_latency_ms, error_rate, request_count, throughput_rpm]

  All features are standardized (z-scored) before fitting so no single
  feature dominates due to scale differences (latency in ms vs error_rate in 0-1).

TRAINING STRATEGY:
  We fit the model on the baseline window (same historical data used for z-score).
  Then score the current window as a single point.

  This means the model is retrained on each detection cycle — fine for V1
  since sklearn's IsolationForest is fast for small datasets (< 500 rows).
  In V2 we'd cache the fitted model with a TTL.

CONTAMINATION:
  Set to 0.05 (5%) — we expect about 5% of data points in a healthy system
  to be flagged as potential anomalies. This is the standard starting value.

SCORE NORMALIZATION:
  sklearn returns decision_function scores in [-0.5, 0.5] range.
  We normalize to [0.0, 1.0]:
    score = max(0.0, 0.5 - decision_function_value)
  Higher output score = more anomalous.
"""

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

MIN_TRAINING_POINTS = 10   # minimum rows to fit the model


@dataclass
class IsolationForestResult:
    is_anomalous:  bool
    score:         float     # 0.0 – 1.0, higher = more anomalous
    raw_score:     float     # sklearn decision_function output (for debugging)


def _build_feature_vector(window) -> list[float]:
    """Extract the 5-feature vector from a MetricAggregate window."""
    return [
        float(window.avg_latency_ms),
        float(window.p95_latency_ms),
        float(window.error_rate),
        float(window.request_count),
        float(window.throughput_rpm),
    ]


def detect_with_isolation_forest(
    baseline_windows: list,
    current_window,
    contamination: float = 0.05,
    anomaly_threshold: float = 0.5,
) -> IsolationForestResult:
    """
    Fit Isolation Forest on baseline_windows and score current_window.

    Parameters:
      baseline_windows: list of MetricAggregate objects (training data)
      current_window:   single MetricAggregate object to score
      contamination:    expected fraction of anomalies in training data
      anomaly_threshold: normalized score above which we flag as anomalous

    Returns IsolationForestResult with is_anomalous=False if insufficient data.
    """
    if len(baseline_windows) < MIN_TRAINING_POINTS:
        return IsolationForestResult(
            is_anomalous=False, score=0.0, raw_score=0.0
        )

    # Build training matrix
    X_train = np.array(
        [_build_feature_vector(w) for w in baseline_windows],
        dtype=np.float64,
    )
    x_current = np.array(
        [_build_feature_vector(current_window)],
        dtype=np.float64,
    )

    # Standardize features — critical so latency_ms (100s) doesn't dominate
    # error_rate (0-1)
    scaler    = StandardScaler()
    X_scaled  = scaler.fit_transform(X_train)
    x_scaled  = scaler.transform(x_current)

    # Fit and score
    model = IsolationForest(
        contamination=contamination,
        random_state=42,        # deterministic results
        n_estimators=100,       # 100 trees is the standard
    )
    model.fit(X_scaled)

    # decision_function returns negative scores for anomalies
    # range roughly [-0.5, 0.5]; more negative = more anomalous
    raw_score = float(model.decision_function(x_scaled)[0])

    # Normalize: score = max(0, 0.5 - raw_score)
    # raw_score = -0.5 → normalized = 1.0 (very anomalous)
    # raw_score =  0.0 → normalized = 0.5 (borderline)
    # raw_score =  0.5 → normalized = 0.0 (normal)
    normalized_score = max(0.0, min(1.0, 0.5 - raw_score))

    return IsolationForestResult(
        is_anomalous = normalized_score >= anomaly_threshold,
        score        = round(normalized_score, 4),
        raw_score    = round(raw_score, 4),
    )
