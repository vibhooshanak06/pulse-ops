"""
Payment API — demo endpoints.

This is the primary endpoint used for failure simulation in Phase 15.
When SIMULATE_LATENCY or SIMULATE_ERRORS is enabled, this endpoint
will deliberately slow down or return errors so the PulseOps anomaly
detection pipeline has something real to detect.

Full implementation and failure simulation in Phase 15.
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/process")
async def process_payment(body: dict) -> dict:
    """Process a payment."""
    return {
        "transaction_id": "TXN-12345",
        "status": "approved",
        "amount": body.get("amount", 0),
        "currency": body.get("currency", "USD"),
    }


@router.get("/status/{transaction_id}")
async def payment_status(transaction_id: str) -> dict:
    """Get payment status."""
    return {
        "transaction_id": transaction_id,
        "status": "approved",
    }
