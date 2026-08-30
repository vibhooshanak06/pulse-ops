"""
PulseOps SDK — lightweight API telemetry for FastAPI applications.

Public API:
    PulseOpsMiddleware  — ASGI middleware, add to your FastAPI app
    PulseOpsConfig      — configuration dataclass

Example:
    from pulseops_sdk import PulseOpsMiddleware, PulseOpsConfig

    app.add_middleware(
        PulseOpsMiddleware,
        config=PulseOpsConfig(
            api_key="po_live_xxxx",
            service_name="payment-service",
        )
    )
"""

from pulseops_sdk.config import PulseOpsConfig
from pulseops_sdk.middleware import PulseOpsMiddleware

__version__ = "0.1.0"
__all__ = ["PulseOpsMiddleware", "PulseOpsConfig"]
