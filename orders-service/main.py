from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uvicorn
import httpx

app = FastAPI(title="Orders Service")

# Configuration
PRODUCTS_SERVICE_URL = "http://products-service:8001"

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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
