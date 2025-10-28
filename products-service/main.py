from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(title="Products Service")

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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
