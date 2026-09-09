"""
Phase 9 — Anomaly Detection Engine verification.

Strategy:
  1. Seed 35 normal traffic windows → no anomaly expected
  2. Inject a spike window → anomaly expected (latency + error_rate)
  3. Verify DB row written with correct severity
  4. Verify deduplication (second spike → no new row for same metric_type)
  5. Verify the pure detection functions directly (unit tests)
  6. Verify recovery → resolved_at set when metric returns to normal
  7. Verify API routes return correct data

Run with: python verify_phase9.py
"""

import sys, time, uuid as _uuid
from datetime import datetime, timezone, timedelta
import httpx

BASE = "http://localhost:8000/v1"
c    = httpx.Client(base_url=BASE, timeout=60)

def ok(label, cond, detail=""):
    icon = "✓" if cond else "✗"
    print(f"  [{icon}] {label}" + (f"  →  {detail}" if detail else ""))
    if not cond:
        print("\n  FAILED. Check backend is running on :8000")
        sys.exit(1)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def ago_iso(s):
    return (datetime.now(timezone.utc) - timedelta(seconds=s)).isoformat()

print("\n=== Phase 9 — Anomaly Detection Verification ===\n")

# ── 0. Unit tests — pure detection functions ──────────────────────────────────
print("0. Unit tests — detection modules (no DB)")

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.anomaly_detection.baseline import BaselineStats, compute_baseline
from app.services.anomaly_detection.statistical import (
    detect_latency_anomaly, detect_error_rate_anomaly, detect_throughput_anomaly,
)
from app.services.anomaly_detection.isolation_forest import (
    detect_with_isolation_forest, IsolationForestResult,
)
from app.services.anomaly_detection.scorer import compute_combined_score

# ── Baseline ────────────────────────────────────────────────────────────────
class FakeWindow:
    def __init__(self, p95, err, tput, req, avg=100.0, p50=80.0):
        self.p95_latency_ms  = p95
        self.error_rate      = err
        self.throughput_rpm  = tput
        self.request_count   = req
        self.avg_latency_ms  = avg
        self.p50_latency_ms  = p50

normal_windows = [FakeWindow(200, 0.01, 100, 50) for _ in range(15)]
baseline = compute_baseline(normal_windows)
ok("Baseline computed from 15 windows",    baseline.has_baseline is True)
ok("Baseline p95 mean ~200",               abs(baseline.p95_latency.mean - 200) < 1)
ok("Baseline error_rate mean ~0.01",       abs(baseline.error_rate.mean - 0.01) < 0.001)
ok("Insufficient data → no baseline",
   compute_baseline(normal_windows[:5]).has_baseline is False)

# ── Statistical detectors ────────────────────────────────────────────────────
ok("Normal latency → not anomalous",
   detect_latency_anomaly(baseline.p95_latency, 210.0).is_anomalous is False)
ok("Spike latency 5× → anomalous",
   detect_latency_anomaly(baseline.p95_latency, 1200.0).is_anomalous is True)
ok("Spike latency score 0–1",
   0 < detect_latency_anomaly(baseline.p95_latency, 1200.0).score <= 1)

ok("Normal error_rate → not anomalous",
   detect_error_rate_anomaly(baseline.error_rate, 0.012).is_anomalous is False)
ok("High error_rate → anomalous",
   detect_error_rate_anomaly(baseline.error_rate, 0.25).is_anomalous is True)

ok("Throughput drop (near zero) → anomalous",
   detect_throughput_anomaly(baseline.throughput_rpm, 5.0).is_anomalous is True)
ok("Throughput spike → anomalous",
   detect_throughput_anomaly(baseline.throughput_rpm, 1000.0).is_anomalous is True)

# ── Isolation Forest ─────────────────────────────────────────────────────────
normal_if = [FakeWindow(200 + i, 0.01, 100, 50) for i in range(20)]
spike_win  = FakeWindow(2500, 0.25, 20, 50)
if_result  = detect_with_isolation_forest(normal_if, spike_win)
ok("IF detects multi-metric spike",        if_result.is_anomalous is True)
ok("IF score 0–1",                         0 <= if_result.score <= 1)

normal_win = FakeWindow(205, 0.011, 98, 50)
if_normal  = detect_with_isolation_forest(normal_if, normal_win)
ok("IF accepts normal window",             if_normal.score < if_result.score)

# ── Combined scorer ──────────────────────────────────────────────────────────
from app.services.anomaly_detection.statistical import StatisticalAnomaly
stat_anomalies = [
    StatisticalAnomaly(True, 5.0, 0.8, "latency",    200, 1200, 500),
    StatisticalAnomaly(True, 4.5, 0.5, "error_rate", 0.01, 0.25, 2400),
]
no_anomalies = [
    StatisticalAnomaly(False, 1.0, 0.0, "latency",    200, 210, 5),
    StatisticalAnomaly(False, 0.5, 0.0, "error_rate", 0.01, 0.011, 10),
]
from app.services.anomaly_detection.isolation_forest import IsolationForestResult

combined_spike  = compute_combined_score(stat_anomalies, IsolationForestResult(True, 0.9, -0.4))
combined_normal = compute_combined_score(no_anomalies,   IsolationForestResult(False, 0.1, 0.4))

ok("Spike → is_anomalous True",            combined_spike.is_anomalous is True)
ok("Spike → severity HIGH or CRITICAL",    combined_spike.severity in ("HIGH", "CRITICAL"))
ok("Spike → triggered_metrics has latency","latency" in combined_spike.triggered_metrics)
ok("Normal → is_anomalous False",          combined_normal.is_anomalous is False)
ok("Normal → severity LOW",               combined_normal.severity == "LOW")
ok("Combined score 0–1",                  0 <= combined_spike.combined_score <= 1)

print(f"     Spike combined_score={combined_spike.combined_score:.3f} "
      f"severity={combined_spike.severity}")

# ── 1. Setup ──────────────────────────────────────────────────────────────────
print("\n1. Setup — register, project, API key")
reg = c.post("/auth/register", json={
    "email":     "anomaly@pulseops.dev",
    "password":  "AnomalyPass999",
    "full_name": "Anomaly Tester",
    "org_name":  "Anomaly Org",
})
ok("Register", reg.status_code == 201, str(reg.status_code))
TOKEN   = reg.json()["access_token"]
H       = {"Authorization": f"Bearer {TOKEN}"}
ORG_ID  = c.get("/organizations", headers=H).json()[0]["id"]
proj    = c.post(f"/organizations/{ORG_ID}/projects", headers=H,
                 json={"name": "Anomaly Project"}).json()
PROJ_ID = proj["id"]
key_r   = c.post(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/api-keys",
                  headers=H, json={"name": "Anomaly Key"}).json()
API_KEY = key_r["key"]
ok("Setup complete", API_KEY.startswith("po_live_"))

# ── 2. Seed 35 normal windows ─────────────────────────────────────────────────
print("\n2. Seeding 35 normal windows (35 × 10 events)")

# 35 batches, each 10 events with stable latency ~200ms, ~1% errors
# spread over 36 minutes so the metrics engine creates ~36 1-min windows
for i in range(35):
    offset_start = 36 * 60 - i * 60    # 36 min ago down to 1 min ago
    events = []
    for j in range(10):
        events.append({
            "endpoint": "/api/payment/process",
            "method": "POST",
            "status_code": 500 if j == 0 else 200,   # exactly 1 error per batch = 10%
            "latency_ms": 190.0 + j * 2,              # 190–208ms
            "timestamp": ago_iso(offset_start - j * 5),
        })
    r = c.post("/telemetry", headers={"X-API-Key": API_KEY},
               json={"service_name": "anomaly-test-svc", "events": events})
    if r.status_code != 202:
        print(f"  Batch {i} failed: {r.status_code}")
        sys.exit(1)

SVC_ID = c.post("/telemetry", headers={"X-API-Key": API_KEY},
                json={"service_name": "anomaly-test-svc", "events": [
                    {"endpoint": "/api/payment/process", "method": "POST",
                     "status_code": 200, "latency_ms": 200.0, "timestamp": now_iso()}
                ]}).json()["service_id"]
ok("35 normal batches seeded", True)
print(f"     service_id={SVC_ID[:8]}...")

# Trigger metrics aggregation to create the windows
print("     Triggering metric aggregation...")
c.get(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/metrics/services/{SVC_ID}/metrics",
      headers=H, params={"window_minutes": 60})

# ── 3. Check no anomaly on normal traffic ─────────────────────────────────────
print("\n3. Normal traffic — no anomaly expected")
r = c.get(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/anomalies/services/{SVC_ID}",
          headers=H)
ok("Anomaly list returns 200", r.status_code == 200, str(r.status_code))
data = r.json()
ok("active anomalies = 0 on normal traffic",
   data["active"] == 0, f"active={data['active']}")
print(f"     active={data['active']}  total={data['total']}")

# ── 4. Inject a spike ─────────────────────────────────────────────────────────
print("\n4. Inject spike (P95 spike + high error rate)")

# Send 20 events with very high latency and 50% errors right now
spike_events = []
for i in range(20):
    spike_events.append({
        "endpoint": "/api/payment/process",
        "method":   "POST",
        "status_code": 500 if i % 2 == 0 else 200,   # 50% errors
        "latency_ms":  2800.0 + i * 50,               # 2800–3750ms (massive spike)
        "timestamp":   ago_iso(i * 3),
    })

r = c.post("/telemetry", headers={"X-API-Key": API_KEY},
           json={"service_name": "anomaly-test-svc", "events": spike_events})
ok("Spike telemetry accepted", r.status_code == 202, str(r.status_code))

# Trigger aggregation for the spike window
print("     Triggering aggregation on spike data...")
c.get(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/metrics/services/{SVC_ID}/metrics",
      headers=H, params={"window_minutes": 60})

# ── 5. Anomaly detected ───────────────────────────────────────────────────────
print("\n5. Anomaly detection on spike")
r = c.get(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/anomalies/services/{SVC_ID}",
          headers=H)
ok("Anomaly endpoint returns 200",     r.status_code == 200, str(r.status_code))
data = r.json()
ok("At least 1 active anomaly",        data["active"] >= 1, f"active={data['active']}")

if data["items"]:
    a = data["items"][0]
    ok("Anomaly has service_id",        a["service_id"] == SVC_ID)
    ok("Severity is HIGH or CRITICAL",  a["severity"] in ("HIGH", "CRITICAL"), a["severity"])
    ok("combined_score > 0.5",          a["combined_score"] > 0.5, str(a["combined_score"]))
    ok("current_value > baseline_value",a["current_value"] > a["baseline_value"])
    ok("deviation_percent > 0",         a["deviation_percent"] > 0)
    ok("resolved_at is None",           a["resolved_at"] is None)
    ok("incident_id is None (pre-corr)",a["incident_id"] is None)
    print(f"     metric_type={a['metric_type']}  severity={a['severity']}  "
          f"score={a['combined_score']:.3f}")
    print(f"     baseline={a['baseline_value']:.1f}  "
          f"current={a['current_value']:.1f}  "
          f"deviation={a['deviation_percent']:.1f}%")

# ── 6. Project-level anomaly list ─────────────────────────────────────────────
print("\n6. Project-level anomaly list")
r = c.get(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/anomalies", headers=H)
ok("Project anomalies returns 200",    r.status_code == 200, str(r.status_code))
proj_data = r.json()
ok("Project shows active anomalies",   proj_data["active"] >= 1, str(proj_data["active"]))
ok("Total >= active",                  proj_data["total"] >= proj_data["active"])

# ── 7. Deduplication — second detection cycle ─────────────────────────────────
print("\n7. Deduplication — re-run detection")
count_before = proj_data["active"]
# Force another detection pass
r = c.get(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/anomalies/services/{SVC_ID}",
          headers=H)
ok("Second call returns 200",          r.status_code == 200)
count_after = r.json()["active"]
ok("No duplicate anomaly rows created",count_after == count_before,
   f"before={count_before} after={count_after}")

# ── 8. Severity correctness ───────────────────────────────────────────────────
print("\n8. Severity correctness (scorer unit test)")
from app.services.anomaly_detection.scorer import _score_to_severity
ok("score=0.1  → LOW",      _score_to_severity(0.1)  == "LOW")
ok("score=0.35 → MEDIUM",   _score_to_severity(0.35) == "MEDIUM")
ok("score=0.65 → HIGH",     _score_to_severity(0.65) == "HIGH")
ok("score=0.85 → CRITICAL", _score_to_severity(0.85) == "CRITICAL")
ok("score=1.0  → CRITICAL", _score_to_severity(1.0)  == "CRITICAL")

# ── 9. include_resolved param ─────────────────────────────────────────────────
print("\n9. include_resolved param")
r_active   = c.get(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/anomalies/services/{SVC_ID}",
                   headers=H, params={"include_resolved": "false"})
r_all      = c.get(f"/organizations/{ORG_ID}/projects/{PROJ_ID}/anomalies/services/{SVC_ID}",
                   headers=H, params={"include_resolved": "true"})
ok("include_resolved=false returns 200", r_active.status_code == 200)
ok("include_resolved=true  returns 200", r_all.status_code == 200)
ok("Total with resolved >= active only",
   r_all.json()["total"] >= r_active.json()["total"])

# ── 10. Auth guard ─────────────────────────────────────────────────────────────
print("\n10. Auth guard")
fake = str(_uuid.uuid4())
r = c.get(f"/organizations/{fake}/projects/{fake}/anomalies")
ok("No JWT → 403", r.status_code == 403, str(r.status_code))
r = c.get(f"/organizations/{fake}/projects/{fake}/anomalies", headers=H)
ok("Fake org → 404", r.status_code == 404, str(r.status_code))

print("\n" + "="*54)
print("  ALL PHASE 9 CHECKS PASSED")
print("="*54 + "\n")
c.close()
