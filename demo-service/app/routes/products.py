"""
Products API — demo endpoints.

Simulates a simple product catalog service.
Full implementation and failure simulation in Phase 15.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_products() -> dict:
    """List all products."""
    return {
        "products": [
            {"id": 1, "name": "Widget Pro", "price": 29.99, "stock": 150},
            {"id": 2, "name": "Gadget Plus", "price": 49.99, "stock": 80},
            {"id": 3, "name": "Doohickey Max", "price": 99.99, "stock": 25},
        ],
        "total": 3,
    }


@router.get("/{product_id}")
async def get_product(product_id: int) -> dict:
    """Get a single product by ID."""
    return {"id": product_id, "name": "Widget Pro", "price": 29.99, "stock": 150}
