"""
Failure scenario simulator.

Controls the demo service's behaviour during Phase 15 demonstrations.
The simulator exposes a simple state object that routes check before
responding, allowing controlled degradation without restarting the service.

Scenarios (Phase 15):
  - normal:        Healthy responses, low latency.
  - high_latency:  Artificial sleep added to payment endpoint.
  - high_errors:   Payment endpoint returns 500 at a configured rate.
  - traffic_spike: Background task floods the endpoint with requests.
  - combined:      Latency + errors simultaneously (realistic degradation).

Phase 15 implementation.
"""

# TODO: Phase 15
