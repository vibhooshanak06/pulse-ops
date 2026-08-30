"""
PulseOps ASGI Middleware.

This is what application developers add to their FastAPI app.
It wraps every HTTP request/response cycle and automatically captures:
  - endpoint path (normalized — /users/123 becomes /users/{id} if using route params)
  - HTTP method
  - response status code
  - latency in milliseconds
  - timestamp

Usage in a FastAPI application:

    from pulseops_sdk import PulseOpsMiddleware, PulseOpsConfig

    app = FastAPI()
    app.add_middleware(
        PulseOpsMiddleware,
        config=PulseOpsConfig(
            api_key="po_live_xxxx",
            service_name="payment-service",
            ingestion_url="http://localhost:8000/v1/telemetry",
        )
    )

ASGI primer (important for understanding this code):
  ASGI middleware receives a `scope`, `receive`, and `send` callable.
  - scope: dict describing the request (type, path, method, headers)
  - receive: async callable to read the request body
  - send: async callable to send the response
  We intercept `send` to capture the response status code without
  modifying it, then pass everything through transparently.
"""

import time
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from pulseops_sdk.client import TelemetryClient
from pulseops_sdk.config import PulseOpsConfig

logger = logging.getLogger("pulseops_sdk.middleware")


class PulseOpsMiddleware(BaseHTTPMiddleware):
    """
    Starlette/FastAPI middleware that instruments every HTTP request.

    Uses BaseHTTPMiddleware which handles the ASGI protocol details for us.
    The trade-off: BaseHTTPMiddleware buffers the full response body in memory,
    which is fine for API responses. For streaming responses (Server-Sent Events,
    file downloads), you'd want a raw ASGI middleware — that's a V2 concern.
    """

    def __init__(self, app: ASGIApp, config: PulseOpsConfig) -> None:
        super().__init__(app)
        self._config = config
        self._client = TelemetryClient(config)
        self._started = False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip paths that should not be instrumented (health checks, docs, etc.)
        if self._should_exclude(request.url.path):
            return await call_next(request)

        # Lazy start — initialize the client on the first real request.
        # This ensures we're inside a running event loop when we call start().
        if not self._started:
            await self._client.start()
            self._started = True

        # ── Capture timing ────────────────────────────────────────────────────
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            # Unhandled exception — treat as a 500 for telemetry purposes,
            # then re-raise so the application's error handlers still run.
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._enqueue_event(request, 500, latency_ms)
            raise

        latency_ms = (time.perf_counter() - start_time) * 1000

        # ── Enqueue telemetry (non-blocking) ──────────────────────────────────
        self._enqueue_event(request, status_code, latency_ms)

        return response

    def _enqueue_event(
        self,
        request: Request,
        status_code: int,
        latency_ms: float,
    ) -> None:
        """Build and enqueue one telemetry event."""
        # Use the matched route path when available (/users/{user_id})
        # rather than the raw path (/users/123).
        # This prevents high-cardinality metrics from per-ID paths.
        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            endpoint = route.path
        else:
            endpoint = request.url.path

        event = TelemetryClient.build_event(
            endpoint=endpoint,
            method=request.method,
            status_code=status_code,
            latency_ms=latency_ms,
        )
        self._client.enqueue(event)

    def _should_exclude(self, path: str) -> bool:
        """Return True if this path should be skipped."""
        return any(path.startswith(excluded) for excluded in self._config.excluded_paths)
