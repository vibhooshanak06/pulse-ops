"""
Orders API — demo endpoints.

Simulates an order management service.
Full implementation and failure simulation in Phase 15.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_orders() -> dict:
    """List recent orders."""
    return {
        "orders": [
            {"id": "ORD-001", "status": "delivered", "total": 79.98},
            {"id": "ORD-002", "status": "processing", "total": 29.99},
            {"id": "ORD-003", "status": "shipped", "total": 149.97},
        ],
        "total": 3,
    }


@router.post("/")
async def create_order(body: dict) -> dict:
    """Create a new order."""
    return {"id": "ORD-NEW", "status": "processing", "total": body.get("total", 0)}
