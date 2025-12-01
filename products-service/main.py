from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import httpx
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from logger import logger, get_trace_id
from middleware import TraceIDMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from metrics import (
    products_created_total,
    products_deleted_total,
    products_stock_gauge,
    product_price_histogram,
    stock_updates_total,
    start_metrics_updater,
    HTTPClientMetrics,
)
from sqlalchemy import select, insert, update, delete

from database import async_session_maker, products, init_db

load_dotenv()

app = FastAPI(title="Products Service")

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


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize database tables on service startup."""
    logger.info("Initializing products database...")
    await init_db()
    logger.info("Products database initialized successfully")

# Configuration
ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders-service:8002")
PORT = int(os.getenv("PORT", "8001"))


class Product(BaseModel):
    name: str
    description: str
    price: float
    stock: int
    category: str


class ProductResponse(Product):
    id: int


@app.get("/")
async def root():
    return {"service": "products-service", "status": "running"}


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
        "service": "products-service"
    }


@app.get("/live")
async def liveness_check():
    """Liveness probe - checks if application is alive"""
    logger.info("Liveness check requested")
    return {
        "status": "alive",
        "service": "products-service",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/ready")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept requests"""
    logger.info("Readiness check requested")

    dependencies = {}
    all_healthy = True

    # Check Orders Service
    orders_status = await check_dependency(ORDERS_SERVICE_URL, "orders-service")
    dependencies["orders-service"] = orders_status
    if orders_status["status"] != "healthy":
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
        "service": "products-service",
        "timestamp": datetime.now().isoformat(),
        "dependencies": dependencies
    }

    if not all_healthy:
        raise HTTPException(status_code=503, detail=response)

    return response


@app.post("/products", response_model=ProductResponse)
async def create_product(product: Product):
    """Create new product and persist it to PostgreSQL."""
    async with async_session_maker() as session:
        stmt = (
            insert(products)
            .values(
                name=product.name,
                description=product.description,
                price=product.price,
                stock=product.stock,
                category=product.category,
                created_at=datetime.utcnow(),
            )
            .returning(products.c.id)
        )
        result = await session.execute(stmt)
        product_id = result.scalar()
        await session.commit()

    # Update Prometheus metrics
    products_created_total.labels(category=product.category).inc()
    product_price_histogram.labels(category=product.category).observe(product.price)
    products_stock_gauge.inc(product.stock)

    logger.info(
        "Product created",
        extra={
            "product_id": product_id,
            "product_name": product.name,
            "price": product.price,
            "stock": product.stock,
            "category": product.category,
        },
    )

    return {
        "id": product_id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "stock": product.stock,
        "category": product.category,
    }


@app.get("/products", response_model=List[ProductResponse])
async def get_products(category: Optional[str] = None):
    """Get list of products, optionally filtered by category."""
    logger.info(
        "Fetching products list",
        extra={"category_filter": category if category else "all"},
    )

    async with async_session_maker() as session:
        stmt = select(products)
        if category is not None:
            stmt = stmt.where(products.c.category == category)
        result = await session.execute(stmt)
        rows = [dict(row._mapping) for row in result]

    response: List[Dict[str, Any]] = []
    for row in rows:
        response.append(
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "price": row["price"],
                "stock": row["stock"],
                "category": row["category"],
            }
        )

    logger.info(
        "Products list retrieved",
        extra={
            "products_count": len(response),
            "category_filter": category if category else "all",
        },
    )

    return response


@app.get("/products/popular")
async def get_popular_products():
    logger.info("Fetching popular products", extra={"action": "fetch_popular_products"})

    # Fetch all orders from orders-service
    async with httpx.AsyncClient() as client:
        try:
            trace_id = get_trace_id()
            headers = {"X-Trace-ID": trace_id} if trace_id else {}

            logger.info(
                "Calling orders-service",
                extra={
                    "target_service": "orders-service",
                    "endpoint": "/orders",
                    "trace_id_sent": trace_id,
                }
            )

            with HTTPClientMetrics("orders-service", "GET") as metrics:
                response = await client.get(
                    f"{ORDERS_SERVICE_URL}/orders",
                    headers=headers,
                    timeout=5.0
                )
                metrics.set_status(response.status_code)

            if response.status_code != 200:
                logger.error(
                    "Failed to fetch orders from orders-service",
                    extra={
                        "status_code": response.status_code,
                        "target_service": "orders-service",
                    }
                )
                raise HTTPException(
                    status_code=503,
                    detail="Failed to fetch orders"
                )

            orders = response.json()
            logger.info(
                "Successfully fetched orders",
                extra={"orders_count": len(orders)}
            )

            # Calculate sales statistics for all products
            product_stats = {}

            for order in orders:
                for item in order.get("items", []):
                    product_id = item["product_id"]
                    if product_id not in product_stats:
                        product_stats[product_id] = {
                            "quantity_sold": 0,
                            "revenue": 0.0,
                            "order_count": 0
                        }

                    product_stats[product_id]["quantity_sold"] += item["quantity"]
                    product_stats[product_id]["revenue"] += item["price"] * item["quantity"]
                    product_stats[product_id]["order_count"] += 1

            # Sort by quantity sold and get top 5
            sorted_products = sorted(
                product_stats.items(),
                key=lambda x: x[1]["quantity_sold"],
                reverse=True
            )[:5]

            # Enrich with product details
            popular_products = []
            for product_id, stats in sorted_products:
                if product_id in products_db:
                    product = products_db[product_id]
                    popular_products.append({
                        "product_id": product_id,
                        "product_name": product["name"],
                        "product_category": product["category"],
                        "current_price": product["price"],
                        "current_stock": product["stock"],
                        "total_quantity_sold": stats["quantity_sold"],
                        "total_revenue": stats["revenue"],
                        "orders_count": stats["order_count"]
                    })

            logger.info(
                "Popular products calculated",
                extra={"popular_products_count": len(popular_products)}
            )

            return {
                "popular_products_count": len(popular_products),
                "products": popular_products
            }

        except httpx.RequestError as e:
            logger.error(
                "Orders service unavailable",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "target_service": "orders-service",
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=503,
                detail="Orders service unavailable"
            )


@app.get("/products/low-stock")
async def get_low_stock_products(threshold: int = 5):
    logger.info(
        "Fetching low-stock products",
        extra={"threshold": threshold}
    )

    # Find products below threshold
    low_stock_products = []

    for product_id, product in products_db.items():
        if product["stock"] <= threshold:
            low_stock_products.append({
                "product_id": product_id,
                "name": product["name"],
                "category": product["category"],
                "current_stock": product["stock"],
                "price": product["price"]
            })

    if not low_stock_products:
        logger.info(
            "No low-stock products found",
            extra={"threshold": threshold}
        )
        return {
            "threshold": threshold,
            "low_stock_count": 0,
            "products": []
        }

    # Enrich with sales data from orders-service to prioritize by popularity
    async with httpx.AsyncClient() as client:
        try:
            with HTTPClientMetrics("orders-service", "GET") as metrics:
                response = await client.get(
                    f"{ORDERS_SERVICE_URL}/orders",
                    timeout=5.0
                )
                metrics.set_status(response.status_code)

            if response.status_code == 200:
                orders = response.json()

                # Calculate sales for each low-stock product
                for product in low_stock_products:
                    product_id = product["product_id"]
                    total_sold = 0

                    for order in orders:
                        for item in order.get("items", []):
                            if item["product_id"] == product_id:
                                total_sold += item["quantity"]

                    product["total_sold"] = total_sold
                    product["urgency_score"] = total_sold / (product["current_stock"] + 1)  # Higher score = more urgent

                # Sort by urgency (popular items with low stock are most urgent)
                low_stock_products.sort(key=lambda x: x.get("urgency_score", 0), reverse=True)

        except httpx.RequestError:
            # If orders service is unavailable, just return products without sales data
            for product in low_stock_products:
                product["total_sold"] = "N/A"
                product["urgency_score"] = "N/A"

    logger.info(
        "Low-stock products retrieved",
        extra={
            "threshold": threshold,
            "low_stock_count": len(low_stock_products),
        }
    )

    return {
        "threshold": threshold,
        "low_stock_count": len(low_stock_products),
        "products": low_stock_products,
        "note": "Products sorted by urgency (high sales + low stock = high urgency)"
    }


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int):
    """Get single product by id from PostgreSQL."""
    logger.info("Fetching product", extra={"product_id": product_id})

    async with async_session_maker() as session:
        stmt = select(products).where(products.c.id == product_id)
        result = await session.execute(stmt)
        row = result.first()

    if not row:
        logger.warning("Product not found", extra={"product_id": product_id})
        raise HTTPException(status_code=404, detail="Product not found")

    data = dict(row._mapping)

    logger.info(
        "Product retrieved",
        extra={
            "product_id": product_id,
            "product_name": data["name"],
        },
    )

    return {
        "id": data["id"],
        "name": data["name"],
        "description": data["description"],
        "price": data["price"],
        "stock": data["stock"],
        "category": data["category"],
    }


@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, product: Product):
    """Update product fields in PostgreSQL."""
    logger.info("Updating product", extra={"product_id": product_id})

    async with async_session_maker() as session:
        # Ensure product exists
        exists_stmt = select(products.c.id).where(products.c.id == product_id)
        exists_result = await session.execute(exists_stmt)
        if not exists_result.first():
            logger.warning(
                "Update failed - product not found", extra={"product_id": product_id}
            )
            raise HTTPException(status_code=404, detail="Product not found")

        stmt = (
            update(products)
            .where(products.c.id == product_id)
            .values(
                name=product.name,
                description=product.description,
                price=product.price,
                stock=product.stock,
                category=product.category,
            )
        )
        await session.execute(stmt)
        await session.commit()

    logger.info(
        "Product updated",
        extra={
            "product_id": product_id,
            "product_name": product.name,
            "price": product.price,
            "stock": product.stock,
        },
    )

    return {
        "id": product_id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "stock": product.stock,
        "category": product.category,
    }


@app.delete("/products/{product_id}")
async def delete_product(product_id: int):
    """Delete product from PostgreSQL."""
    logger.info("Deleting product", extra={"product_id": product_id})

    async with async_session_maker() as session:
        stmt = select(products).where(products.c.id == product_id)
        result = await session.execute(stmt)
        row = result.first()

        if not row:
            logger.warning(
                "Delete failed - product not found",
                extra={"product_id": product_id},
            )
            raise HTTPException(status_code=404, detail="Product not found")

        data = dict(row._mapping)

        # Update Prometheus metrics before deleting
        products_deleted_total.labels(category=data["category"]).inc()
        products_stock_gauge.dec(data["stock"])

        del_stmt = delete(products).where(products.c.id == product_id)
        await session.execute(del_stmt)
        await session.commit()

    logger.info(
        "Product deleted",
        extra={
            "product_id": product_id,
            "product_name": data["name"],
        },
    )

    return {"message": "Product deleted successfully"}


@app.patch("/products/{product_id}/stock")
async def update_stock(product_id: int, quantity: int):
    """Change product stock value in PostgreSQL."""
    async with async_session_maker() as session:
        stmt = select(products).where(products.c.id == product_id)
        result = await session.execute(stmt)
        row = result.first()

        if not row:
            logger.warning(
                "Stock update failed - product not found",
                extra={"product_id": product_id},
            )
            raise HTTPException(status_code=404, detail="Product not found")

        data = dict(row._mapping)
        old_stock = data["stock"]
        new_stock = old_stock + quantity

        if new_stock < 0:
            logger.warning(
                "Stock update failed - insufficient stock",
                extra={
                    "product_id": product_id,
                    "current_stock": old_stock,
                    "requested_quantity": quantity,
                },
            )
            raise HTTPException(status_code=400, detail="Insufficient stock")

        upd_stmt = (
            update(products)
            .where(products.c.id == product_id)
            .values(stock=new_stock)
        )
        await session.execute(upd_stmt)
        await session.commit()

    # Update Prometheus metrics
    operation = "increase" if quantity > 0 else "decrease"
    stock_updates_total.labels(
        product_id=str(product_id),
        operation=operation,
    ).inc()
    products_stock_gauge.inc(quantity)

    logger.info(
        "Stock updated",
        extra={
            "product_id": product_id,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "quantity_change": quantity,
        },
    )

    return {"id": product_id, "stock": new_stock}


@app.get("/products/{product_id}/stats")
async def get_product_stats(product_id: int):
    logger.info("Fetching product stats", extra={"product_id": product_id})

    if product_id not in products_db:
        logger.warning("Product stats failed - product not found", extra={"product_id": product_id})
        raise HTTPException(status_code=404, detail="Product not found")

    product = products_db[product_id]

    # Fetch all orders from orders-service
    async with httpx.AsyncClient() as client:
        try:
            trace_id = get_trace_id()
            headers = {"X-Trace-ID": trace_id} if trace_id else {}

            with HTTPClientMetrics("orders-service", "GET") as metrics:
                response = await client.get(
                    f"{ORDERS_SERVICE_URL}/orders",
                    timeout=5.0
                )
                metrics.set_status(response.status_code)

            if response.status_code != 200:
                logger.error(
                    "Failed to fetch orders for product stats",
                    extra={"product_id": product_id, "status_code": response.status_code}
                )
                raise HTTPException(
                    status_code=503,
                    detail="Failed to fetch orders"
                )

            orders = response.json()

            # Calculate statistics for this product
            total_quantity_sold = 0
            total_revenue = 0.0
            order_count = 0

            for order in orders:
                for item in order.get("items", []):
                    if item["product_id"] == product_id:
                        total_quantity_sold += item["quantity"]
                        total_revenue += item["price"] * item["quantity"]
                        order_count += 1

            logger.info(
                "Product stats calculated",
                extra={
                    "product_id": product_id,
                    "total_quantity_sold": total_quantity_sold,
                    "total_revenue": total_revenue,
                    "orders_count": order_count,
                }
            )

            return {
                "product_id": product_id,
                "product_name": product["name"],
                "product_category": product["category"],
                "current_stock": product["stock"],
                "current_price": product["price"],
                "total_quantity_sold": total_quantity_sold,
                "total_revenue": total_revenue,
                "orders_count": order_count
            }

        except httpx.RequestError as e:
            logger.error(
                "Orders service unavailable for product stats",
                extra={
                    "error": str(e),
                    "product_id": product_id,
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=503,
                detail="Orders service unavailable"
            )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)