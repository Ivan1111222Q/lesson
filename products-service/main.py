from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Products Service")

# Configuration
ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders-service:8002")
PORT = int(os.getenv("PORT", "8001"))

# In-memory database for demo
products_db = {}
product_id_counter = 1


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


@app.post("/products", response_model=ProductResponse)
async def create_product(product: Product):
    global product_id_counter
    product_id = product_id_counter
    products_db[product_id] = product.model_dump()
    product_id_counter += 1
    return {"id": product_id, **products_db[product_id]}


@app.get("/products", response_model=List[ProductResponse])
async def get_products(category: Optional[str] = None):
    products = []
    for product_id, product in products_db.items():
        if category is None or product.get("category") == category:
            products.append({"id": product_id, **product})
    return products


@app.get("/products/popular")
async def get_popular_products():
    # Fetch all orders from orders-service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{ORDERS_SERVICE_URL}/orders",
                timeout=5.0
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=503,
                    detail="Failed to fetch orders"
                )

            orders = response.json()

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

            return {
                "popular_products_count": len(popular_products),
                "products": popular_products
            }

        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Orders service unavailable"
            )


@app.get("/products/low-stock")
async def get_low_stock_products(threshold: int = 5):
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
        return {
            "threshold": threshold,
            "low_stock_count": 0,
            "products": []
        }

    # Enrich with sales data from orders-service to prioritize by popularity
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{ORDERS_SERVICE_URL}/orders",
                timeout=5.0
            )

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

    return {
        "threshold": threshold,
        "low_stock_count": len(low_stock_products),
        "products": low_stock_products,
        "note": "Products sorted by urgency (high sales + low stock = high urgency)"
    }


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int):
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"id": product_id, **products_db[product_id]}


@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: int, product: Product):
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    products_db[product_id] = product.model_dump()
    return {"id": product_id, **products_db[product_id]}


@app.delete("/products/{product_id}")
async def delete_product(product_id: int):
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    del products_db[product_id]
    return {"message": "Product deleted successfully"}


@app.patch("/products/{product_id}/stock")
async def update_stock(product_id: int, quantity: int):
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")

    product = products_db[product_id]
    new_stock = product["stock"] + quantity

    if new_stock < 0:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    products_db[product_id]["stock"] = new_stock
    return {"id": product_id, "stock": new_stock}


@app.get("/products/{product_id}/stats")
async def get_product_stats(product_id: int):
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")

    product = products_db[product_id]

    # Fetch all orders from orders-service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{ORDERS_SERVICE_URL}/orders",
                timeout=5.0
            )
            if response.status_code != 200:
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

        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Orders service unavailable"
            )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
