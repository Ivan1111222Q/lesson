from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uvicorn
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Orders Service")

# Configuration
PRODUCTS_SERVICE_URL = os.getenv("PRODUCTS_SERVICE_URL", "http://products-service:8001")
USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://users-service:8003")
PORT = int(os.getenv("PORT", "8002"))

# In-memory database for demo
orders_db = {}
order_id_counter = 1


class OrderItem(BaseModel):
    product_id: int
    quantity: int
    price: float


class Order(BaseModel):
    user_id: int
    items: List[OrderItem]
    status: str = "pending"


class OrderResponse(Order):
    id: int
    total: float
    created_at: str


@app.get("/")
async def root():
    return {"service": "orders-service", "status": "running"}


@app.post("/orders", response_model=OrderResponse)
async def create_order(order: Order):
    global order_id_counter

    # Verify user exists
    async with httpx.AsyncClient() as client:
        try:
            user_response = await client.get(
                f"{USERS_SERVICE_URL}/users/{order.user_id}",
                timeout=5.0
            )
            if user_response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"User {order.user_id} not found"
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Users service unavailable"
            )

    # Verify products and check stock
    total = 0.0
    async with httpx.AsyncClient() as client:
        for item in order.items:
            try:
                response = await client.get(
                    f"{PRODUCTS_SERVICE_URL}/products/{item.product_id}",
                    timeout=5.0
                )
                if response.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Product {item.product_id} not found"
                    )
                product = response.json()

                if product["stock"] < item.quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient stock for product {item.product_id}"
                    )

                # Update stock
                await client.patch(
                    f"{PRODUCTS_SERVICE_URL}/products/{item.product_id}/stock",
                    params={"quantity": -item.quantity},
                    timeout=5.0
                )

                total += item.price * item.quantity

            except httpx.RequestError:
                raise HTTPException(
                    status_code=503,
                    detail="Products service unavailable"
                )

    order_id = order_id_counter
    order_data = order.model_dump()
    order_data["created_at"] = datetime.now().isoformat()
    order_data["total"] = total
    orders_db[order_id] = order_data
    order_id_counter += 1

    return {"id": order_id, **orders_db[order_id]}


@app.get("/orders", response_model=List[OrderResponse])
async def get_orders(user_id: Optional[int] = None):
    orders = []
    for order_id, order in orders_db.items():
        if user_id is None or order.get("user_id") == user_id:
            orders.append({"id": order_id, **order})
    return orders


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int):
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"id": order_id, **orders_db[order_id]}


@app.patch("/orders/{order_id}/status")
async def update_order_status(order_id: int, status: str):
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")

    valid_statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    orders_db[order_id]["status"] = status
    return {"id": order_id, "status": status}


@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int):
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")

    order = orders_db[order_id]

    # Check if order can be cancelled
    if order["status"] not in ["pending", "processing"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status '{order['status']}'. Only pending or processing orders can be cancelled."
        )

    # Return products to stock
    async with httpx.AsyncClient() as client:
        for item in order["items"]:
            try:
                # Return stock by adding back the quantity
                response = await client.patch(
                    f"{PRODUCTS_SERVICE_URL}/products/{item['product_id']}/stock",
                    params={"quantity": item["quantity"]},  # Positive to add back
                    timeout=5.0
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Failed to return stock for product {item['product_id']}"
                    )

            except httpx.RequestError:
                raise HTTPException(
                    status_code=503,
                    detail="Products service unavailable"
                )

    # Update order status to cancelled
    orders_db[order_id]["status"] = "cancelled"

    return {
        "id": order_id,
        "status": "cancelled",
        "message": "Order cancelled successfully. Stock returned to inventory.",
        "returned_items": len(order["items"])
    }


@app.get("/orders/{order_id}/details")
async def get_order_details(order_id: int):
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")

    order = orders_db[order_id]

    # Enrich order items with product details
    enriched_items = []
    async with httpx.AsyncClient() as client:
        for item in order["items"]:
            try:
                product_response = await client.get(
                    f"{PRODUCTS_SERVICE_URL}/products/{item['product_id']}",
                    timeout=5.0
                )
                if product_response.status_code == 200:
                    product = product_response.json()
                    enriched_items.append({
                        "product_id": item["product_id"],
                        "product_name": product["name"],
                        "product_description": product["description"],
                        "product_category": product["category"],
                        "current_price": product["price"],
                        "ordered_price": item["price"],
                        "quantity": item["quantity"],
                        "subtotal": item["price"] * item["quantity"]
                    })
                else:
                    # Product might be deleted, show minimal info
                    enriched_items.append({
                        "product_id": item["product_id"],
                        "product_name": "Product not found",
                        "product_description": "",
                        "product_category": "",
                        "current_price": 0,
                        "ordered_price": item["price"],
                        "quantity": item["quantity"],
                        "subtotal": item["price"] * item["quantity"]
                    })
            except httpx.RequestError:
                # Service unavailable, show minimal info
                enriched_items.append({
                    "product_id": item["product_id"],
                    "product_name": "Service unavailable",
                    "product_description": "",
                    "product_category": "",
                    "current_price": 0,
                    "ordered_price": item["price"],
                    "quantity": item["quantity"],
                    "subtotal": item["price"] * item["quantity"]
                })

    return {
        "id": order_id,
        "user_id": order["user_id"],
        "items": enriched_items,
        "status": order["status"],
        "total": order["total"],
        "created_at": order["created_at"]
    }


@app.get("/orders/stats/revenue")
async def get_revenue_stats():
    if not orders_db:
        return {
            "total_orders": 0,
            "total_revenue": 0.0,
            "average_order_value": 0.0,
            "orders_by_status": {},
            "revenue_by_status": {}
        }

    total_revenue = 0.0
    total_orders = len(orders_db)
    orders_by_status = {}
    revenue_by_status = {}

    for order in orders_db.values():
        status = order["status"]
        order_total = order["total"]

        # Count orders by status
        orders_by_status[status] = orders_by_status.get(status, 0) + 1

        # Sum revenue by status (only count non-cancelled orders for revenue)
        if status != "cancelled":
            total_revenue += order_total
            revenue_by_status[status] = revenue_by_status.get(status, 0.0) + order_total

    average_order_value = total_revenue / total_orders if total_orders > 0 else 0.0

    # Get completed orders count (delivered)
    completed_orders = orders_by_status.get("delivered", 0)

    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": orders_by_status.get("cancelled", 0),
        "total_revenue": round(total_revenue, 2),
        "average_order_value": round(average_order_value, 2),
        "orders_by_status": orders_by_status,
        "revenue_by_status": {k: round(v, 2) for k, v in revenue_by_status.items()}
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
