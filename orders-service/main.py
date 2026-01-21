from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uvicorn
import httpx
import os
import time

from dotenv import load_dotenv
from logger import logger, get_trace_id
from middleware import TraceIDMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from metrics import (
    orders_created_total,
    orders_cancelled_total,
    order_items_total,
    order_value_histogram,
    revenue_gauge,
    order_status_changes_total,
    start_metrics_updater,
    HTTPClientMetrics,
)
from sqlalchemy import select, insert, update, delete

from database import async_session_maker, orders, init_db, fetch_order

load_dotenv()

app = FastAPI(title="Orders Service")

start_metrics_updater(interval=10)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TraceIDMiddleware)

# Initialize Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Configuration
PRODUCTS_SERVICE_URL = os.getenv("PRODUCTS_SERVICE_URL", "http://products-service:8001")
USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://users-service:8003")
PORT = int(os.getenv("PORT", "8002"))


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize orders database on startup."""
    logger.info("Initializing orders database...")
    await init_db()
    logger.info("Orders database initialized successfully")


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


async def check_dependency(url: str, service_name: str) -> Dict[str, Any]:
    """Check if a dependent service is healthy"""
    start_time = time.time()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/health", timeout=2.0)
            response_time_ms = round((time.time() - start_time) * 1000, 2)

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "response_time_ms": response_time_ms
                }
            else:
                return {
                    "status": "unhealthy",
                    "status_code": response.status_code,
                    "response_time_ms": response_time_ms
                }
    except Exception as e:
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": response_time_ms
        }


@app.get("/health")
async def health_check():
    """Basic health check - returns 200 if service is running"""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "service": "orders-service"
    }


@app.get("/live")
async def liveness_check():
    """Liveness probe - checks if application is alive"""
    logger.info("Liveness check requested")
    return {
        "status": "alive",
        "service": "orders-service",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/ready")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept requests"""
    logger.info("Readiness check requested")

    dependencies = {}
    all_healthy = True

    # Check Products Service
    products_status = await check_dependency(PRODUCTS_SERVICE_URL, "products-service")
    dependencies["products-service"] = products_status
    if products_status["status"] != "healthy":
        all_healthy = False

    # Check Users Service
    users_status = await check_dependency(USERS_SERVICE_URL, "users-service")
    dependencies["users-service"] = users_status
    if users_status["status"] != "healthy":
        all_healthy = False

    status = "ready" if all_healthy else "not_ready"

    logger.info(
        "Readiness check completed",
        extra={
            "status": status,
            "dependencies": dependencies
        }
    )

    response = {
        "status": status,
        "service": "orders-service",
        "timestamp": datetime.now().isoformat(),
        "dependencies": dependencies
    }

    if not all_healthy:
        raise HTTPException(status_code=503, detail=response)

    return response


@app.post("/orders", response_model=OrderResponse)
async def create_order(order: Order):
    logger.info(
        "Creating order",
        extra={
            "user_id": order.user_id,
            "items_count": len(order.items),
        }
    )

    # Verify user exists
    async with httpx.AsyncClient() as client:
        try:
            trace_id = get_trace_id()
            headers = {"X-Trace-ID": trace_id} if trace_id else {}

            logger.info(
                "Verifying user exists",
                extra={
                    "user_id": order.user_id,
                    "target_service": "users-service",
                }
            )

            with HTTPClientMetrics("users-service", "GET") as metrics:
                user_response = await client.get(
                    f"{USERS_SERVICE_URL}/users/{order.user_id}",
                    headers=headers,
                    timeout=5.0
                )
                metrics.set_status(user_response.status_code)

            if user_response.status_code == 404:
                logger.warning(
                    "User not found",
                    extra={"user_id": order.user_id}
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"User {order.user_id} not found"
                )

            logger.info("User verified", extra={"user_id": order.user_id})

        except httpx.RequestError as e:
            logger.error(
                "Users service unavailable",
                extra={
                    "error": str(e),
                    "target_service": "users-service",
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=503,
                detail="Users service unavailable"
            )

    # Verify products and check stock
    total = 0.0
    async with httpx.AsyncClient() as client:
        trace_id = get_trace_id()
        headers = {"X-Trace-ID": trace_id} if trace_id else {}

        for item in order.items:
            try:
                logger.info(
                    "Verifying product and stock",
                    extra={
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                    }
                )

                with HTTPClientMetrics("products-service", "GET") as metrics:
                    response = await client.get(
                        f"{PRODUCTS_SERVICE_URL}/products/{item.product_id}",
                        headers=headers,
                        timeout=5.0
                    )
                    metrics.set_status(response.status_code)

                if response.status_code == 404:
                    logger.warning(
                        "Product not found",
                        extra={"product_id": item.product_id}
                    )
                    raise HTTPException(
                        status_code=404,
                        detail=f"Product {item.product_id} not found"
                    )
                product = response.json()

                if product["stock"] < item.quantity:
                    logger.warning(
                        "Insufficient stock",
                        extra={
                            "product_id": item.product_id,
                            "requested": item.quantity,
                            "available": product["stock"],
                        }
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient stock for product {item.product_id}"
                    )

                # Update stock
                logger.info(
                    "Updating product stock",
                    extra={
                        "product_id": item.product_id,
                        "quantity_change": -item.quantity,
                    }
                )

                with HTTPClientMetrics("products-service", "PATCH") as metrics:
                    stock_response = await client.patch(
                        f"{PRODUCTS_SERVICE_URL}/products/{item.product_id}/stock",
                        params={"quantity": -item.quantity},
                        headers=headers,
                        timeout=5.0
                    )
                    metrics.set_status(stock_response.status_code)

                total += item.price * item.quantity

            except httpx.RequestError as e:
                logger.error(
                    "Products service unavailable",
                    extra={
                        "error": str(e),
                        "target_service": "products-service",
                        "product_id": item.product_id,
                    },
                    exc_info=True
                )
                raise HTTPException(
                    status_code=503,
                    detail="Products service unavailable"
                )

    # Persist order in PostgreSQL
    async with async_session_maker() as session:
        stmt = (
            insert(orders)
            .values(
                user_id=order.user_id,
                items=[item.model_dump() for item in order.items],
                status=order.status,
                total=total,
                created_at=datetime.now(),
            )
            .returning(orders.c.id)
        )
        result = await session.execute(stmt)
        order_id = result.scalar()
        await session.commit()

    # Update Prometheus metrics
    orders_created_total.labels(status=order.status).inc()
    order_value_histogram.observe(total)
    revenue_gauge.inc(total)
    order_items_total.inc(len(order.items))

    logger.info(
        "Order created successfully",
        extra={
            "order_id": order_id,
            "user_id": order.user_id,
            "total": total,
            "items_count": len(order.items),
        },
    )

    return {
        "id": order_id,
        "user_id": order.user_id,
        "items": [item.model_dump() for item in order.items],
        "status": order.status,
        "total": total,
        "created_at": datetime.now().isoformat(),
    }


@app.get("/orders", response_model=List[OrderResponse])
async def get_orders(user_id: Optional[int] = None):
    logger.info(
        "Fetching orders",
        extra={"user_id_filter": user_id if user_id else "all"}
    )

    async with async_session_maker() as session:
        stmt = select(orders)
        if user_id is not None:
            stmt = stmt.where(orders.c.user_id == user_id)
        result = await session.execute(stmt)
        rows = [dict(row._mapping) for row in result]

    response: List[Dict[str, Any]] = []
    for row in rows:
        response.append(
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "items": row["items"],
            "status": row["status"],
            "total": row["total"],
            "created_at": row["created_at"].isoformat() if isinstance(row["created_at"], datetime) else row["created_at"],
        }
    )

    logger.info(
        "Orders retrieved",
        extra={
            "orders_count": len(response),
            "user_id_filter": user_id if user_id else "all",
        },
    )

    return response


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: int):
    logger.info("Fetching order", extra={"order_id": order_id})

    async with async_session_maker() as session:
        data = await fetch_order(session, order_id)

    if not data:
        logger.warning("Order not found", extra={"order_id": order_id})
        raise HTTPException(status_code=404, detail="Order not found")

    logger.info(
        "Order retrieved",
        extra={
            "order_id": order_id,
            "user_id": data["user_id"],
            "status": data["status"],
        },
    )

    return {
        "id": data["id"],
        "user_id": data["user_id"],
        "items": data["items"],
        "status": data["status"],
        "total": data["total"],
        "created_at": data["created_at"].isoformat() if isinstance(data["created_at"], datetime) else data["created_at"],
    }


@app.patch("/orders/{order_id}/status")
async def update_order_status(order_id: int, status: str):
    """Обновление статуса заказа"""
    logger.info(
        "Updating order status",
        extra={"order_id": order_id, "new_status": status}
    )

    async with async_session_maker() as session:
        data = await fetch_order(session, order_id)

        if not data:
            logger.warning("Status update failed - order not found", extra={"order_id": order_id})
            raise HTTPException(status_code=404, detail="Order not found")

    valid_statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
    if status not in valid_statuses:
        logger.warning(
            "Status update failed - invalid status",
            extra={"order_id": order_id, "attempted_status": status}
        )
        raise HTTPException(status_code=400, detail="Invalid status")

    old_status = data["status"]

    async with async_session_maker() as session:
        stmt = (
            update(orders)
            .where(orders.c.id == order_id)
            .values(status=status)
        )
        await session.execute(stmt)
        await session.commit()

    # Update Prometheus metrics
    order_status_changes_total.labels(
        from_status=old_status,
        to_status=status
    ).inc()

    logger.info(
        "Order status updated",
        extra={
            "order_id": order_id,
            "old_status": old_status,
            "new_status": status,
        }
    )

    return {"id": order_id, "status": status}


@app.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int):
    async with async_session_maker() as session:
        order = await fetch_order(session, order_id)

    if not order:
        logger.warning("Cancel order failed - order not found", extra={"order_id": order_id})
        raise HTTPException(status_code=404, detail="Order not found")

    logger.info(
        "Cancelling order",
        extra={
            "order_id": order_id,
            "current_status": order["status"],
            "items_count": len(order["items"]),
        }
    )

    # Check if order can be cancelled
    if order["status"] not in ["pending", "processing"]:
        logger.warning(
            "Cancel order failed - invalid status",
            extra={
                "order_id": order_id,
                "status": order["status"],
            }
        )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status '{order['status']}'. Only pending or processing orders can be cancelled."
        )

    # Return products to stock
    async with httpx.AsyncClient() as client:
        trace_id = get_trace_id()
        headers = {"X-Trace-ID": trace_id} if trace_id else {}

        for item in order["items"]:
            try:
                logger.info(
                    "Returning stock to product",
                    extra={
                        "order_id": order_id,
                        "product_id": item["product_id"],
                        "quantity": item["quantity"],
                    }
                )

                # Return stock by adding back the quantity
                with HTTPClientMetrics("products-service", "PATCH") as metrics:
                    response = await client.patch(
                        f"{PRODUCTS_SERVICE_URL}/products/{item['product_id']}/stock",
                        params={"quantity": item["quantity"]},  # Positive to add back
                        headers=headers,
                        timeout=5.0
                    )
                    metrics.set_status(response.status_code)

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Failed to return stock for product {item['product_id']}"
                    )

            except httpx.RequestError as e:
                logger.error(
                    "Products service unavailable during cancel",
                    extra={
                        "error": str(e),
                        "order_id": order_id,
                        "product_id": item["product_id"],
                    },
                    exc_info=True
                )
                raise HTTPException(
                    status_code=503,
                    detail="Products service unavailable"
                )

    # Update order status to cancelled
    old_status = order["status"]

    async with async_session_maker() as session:
        stmt = (
            update(orders)
            .where(orders.c.id == order_id)
            .values(status="cancelled")
        )
        await session.execute(stmt)
        await session.commit()

    # Update Prometheus metrics
    orders_cancelled_total.inc()
    order_status_changes_total.labels(
        from_status=old_status,
        to_status="cancelled"
    ).inc()
    # Decrease revenue by order total
    revenue_gauge.dec(order["total"])

    logger.info(
        "Order cancelled successfully",
        extra={
            "order_id": order_id,
            "returned_items": len(order["items"]),
        }
    )

    return {
        "id": order_id,
        "status": "cancelled",
        "message": "Order cancelled successfully. Stock returned to inventory.",
        "returned_items": len(order["items"])
    }


@app.get("/orders/{order_id}/details")
async def get_order_details(order_id: int):
    logger.info("Fetching order details", extra={"order_id": order_id})

    async with async_session_maker() as session:
        order = await fetch_order(session, order_id)

    if not order:
        logger.warning("Order details failed - order not found", extra={"order_id": order_id})
        raise HTTPException(status_code=404, detail="Order not found")

    # Enrich order items with product details
    enriched_items = []
    async with httpx.AsyncClient() as client:
        trace_id = get_trace_id()
        headers = {"X-Trace-ID": trace_id} if trace_id else {}

        for item in order["items"]:
            try:
                with HTTPClientMetrics("products-service", "GET") as metrics:
                    product_response = await client.get(
                        f"{PRODUCTS_SERVICE_URL}/products/{item['product_id']}",
                        headers=headers,
                        timeout=5.0
                    )
                    metrics.set_status(product_response.status_code)

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

    logger.info(
        "Order details retrieved",
        extra={
            "order_id": order_id,
            "enriched_items_count": len(enriched_items),
        }
    )

    return {
        "id": order_id,
        "user_id": order["user_id"],
        "items": enriched_items,
        "status": order["status"],
        "total": order["total"],
        "created_at": order["created_at"].isoformat() if isinstance(order["created_at"], datetime) else order["created_at"],
    }


@app.get("/orders/stats/revenue")
async def get_revenue_stats():
    logger.info("Fetching revenue statistics")

    async with async_session_maker() as session:
        result = await session.execute(select(orders))
        rows = [dict(r._mapping) for r in result]

    if not rows:
        logger.info("Revenue statistics - no orders found")
        return {
            "total_orders": 0,
            "total_revenue": 0.0,
            "average_order_value": 0.0,
            "orders_by_status": {},
            "revenue_by_status": {},
        }

    total_revenue = 0.0
    total_orders = len(rows)
    orders_by_status: Dict[str, int] = {}
    revenue_by_status: Dict[str, float] = {}

    for order in rows:
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

    logger.info(
        "Revenue statistics calculated",
        extra={
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "cancelled_orders": orders_by_status.get("cancelled", 0),
            "total_revenue": round(total_revenue, 2),
        }
    )

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