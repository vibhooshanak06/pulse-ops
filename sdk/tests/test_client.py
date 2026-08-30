"""
SDK client unit tests — Phase 16 will add full coverage.
Structural smoke test only for now.
"""

from pulseops_sdk.client import TelemetryClient


def test_build_event_structure():
    """Verify that build_event returns the expected keys."""
    event = TelemetryClient.build_event(
        endpoint="/api/payment",
        method="POST",
        status_code=200,
        latency_ms=123.45,
    )
    assert event["endpoint"] == "/api/payment"
    assert event["method"] == "POST"
    assert event["status_code"] == 200
    assert event["latency_ms"] == 123.45
    assert "timestamp" in event


def test_build_event_method_uppercased():
    """Method should always be uppercased."""
    event = TelemetryClient.build_event(
        endpoint="/api/test",
        method="get",
        status_code=200,
        latency_ms=10.0,
    )
    assert event["method"] == "GET"
