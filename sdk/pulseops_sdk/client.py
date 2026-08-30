"""
Telemetry HTTP client.

Responsibilities:
  1. Accept individual telemetry events from the middleware.
  2. Accumulate them in an in-memory buffer (batch).
  3. Flush the batch to the PulseOps ingestion API either when:
       - The batch reaches batch_size, OR
       - The flush_interval_seconds timer fires.
  4. Never block the application's request-response cycle.
     All network I/O happens in a background asyncio task.

Design note on fire-and-forget:
  We use asyncio.create_task() for flushes. If the ingestion API is
  down, we log the error and discard the batch — we never let telemetry
  delivery affect the observed application's availability.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from pulseops_sdk.config import PulseOpsConfig

logger = logging.getLogger("pulseops_sdk.client")


class TelemetryClient:
    """
    Async telemetry client with in-memory batching.

    Usage (managed by the middleware — you rarely instantiate this directly):
        client = TelemetryClient(config)
        await client.start()          # called once at app startup
        client.enqueue(event_dict)    # called per request
        await client.stop()           # called at app shutdown — flushes remaining
    """

    def __init__(self, config: PulseOpsConfig) -> None:
        self._config = config
        self._buffer: list[dict] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False
        self._http_client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Initialize HTTP client and start the periodic flush loop."""
        self._http_client = httpx.AsyncClient(
            timeout=self._config.timeout_seconds,
            headers={
                "X-API-Key": self._config.api_key,
                "Content-Type": "application/json",
            },
        )
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            f"PulseOps SDK started | service={self._config.service_name} "
            f"| target={self._config.ingestion_url}"
        )

    async def stop(self) -> None:
        """Flush remaining events and shut down cleanly."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush — send whatever is left in the buffer
        await self._flush()

        if self._http_client:
            await self._http_client.aclose()

        logger.info("PulseOps SDK stopped.")

    def enqueue(self, event: dict) -> None:
        """
        Add a telemetry event to the buffer.

        This is intentionally synchronous so the middleware can call it
        without awaiting. The actual network I/O happens in the flush loop.
        The asyncio.create_task pattern is safe here because we're always
        inside a running event loop when serving requests.
        """
        # Use call_soon_threadsafe-compatible approach:
        # We append to the list directly (GIL-safe for single appends)
        # and check the batch size without blocking.
        self._buffer.append(event)

        # If batch is full, schedule an immediate flush
        if len(self._buffer) >= self._config.batch_size:
            asyncio.create_task(self._flush())

    async def _flush_loop(self) -> None:
        """Periodic background flush — runs every flush_interval_seconds."""
        while self._running:
            await asyncio.sleep(self._config.flush_interval_seconds)
            await self._flush()

    async def _flush(self) -> None:
        """
        Drain the buffer and POST the batch to the ingestion API.

        We swap the buffer under a lock so new events can continue
        arriving while the HTTP request is in flight.
        """
        async with self._lock:
            if not self._buffer:
                return
            batch = self._buffer.copy()
            self._buffer.clear()

        if not self._http_client:
            return

        payload = {
            "service_name": self._config.service_name,
            "events": batch,
        }

        try:
            response = await self._http_client.post(
                self._config.ingestion_url,
                json=payload,
            )
            if response.status_code not in (200, 201, 202):
                logger.warning(
                    f"Telemetry ingestion returned {response.status_code}: "
                    f"{response.text[:200]}"
                )
            else:
                logger.debug(f"Flushed {len(batch)} telemetry events.")
        except httpx.RequestError as exc:
            # Network error — log and discard. Never raise.
            # The observed application must not be affected by telemetry failures.
            logger.warning(f"Telemetry flush failed (network): {exc}")
        except Exception as exc:
            logger.warning(f"Telemetry flush failed (unexpected): {exc}")

    @staticmethod
    def build_event(
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
    ) -> dict:
        """
        Build a telemetry event dict.

        Called by the middleware after each request completes.
        """
        return {
            "endpoint": endpoint,
            "method": method.upper(),
            "status_code": status_code,
            "latency_ms": round(latency_ms, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
