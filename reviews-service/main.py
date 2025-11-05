from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uvicorn
import httpx
import os
import time
import uuid
import aiofiles
from pathlib import Path
from PIL import Image
import io
import sqlalchemy
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, MetaData, create_engine, select, func

from dotenv import load_dotenv
from logger import logger, get_trace_id
from middleware import TraceIDMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from metrics import (
    reviews_created_total,
    reviews_deleted_total,
    reviews_with_photos_total,
    photos_uploaded_total,
    photos_deleted_total,
    photos_storage_size_bytes,
    average_product_rating,
    HTTPClientMetrics
)

load_dotenv()

app = FastAPI(title="Reviews Service")

POSTGRES_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)

engine = create_engine(POSTGRES_URL)
metadata = MetaData()

reviews = Table(
    "reviews",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, nullable=False),
    Column("product_id", Integer, nullable=False),
    Column("order_id", Integer, nullable=False),
    Column("rating", Integer, nullable=False),
    Column("text", String, nullable=False),
    Column("photos", String, nullable=True),  # comma-separated filenames
    Column("is_verified_purchase", Boolean, default=False),
    Column("created_at", DateTime, default=datetime.utcnow),
)

metadata.create_all(engine)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TraceIDMiddleware)

Instrumentator().instrument(app).expose(app)

USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://users-service:8003")
PRODUCTS_SERVICE_URL = os.getenv("PRODUCTS_SERVICE_URL", "http://products-service:8001")
ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders-service:8002")
PORT = int(os.getenv("PORT", "8004"))
UPLOAD_DIR = Path("/app/uploads")
MAX_PHOTOS = 5
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    order_id: int
    rating: int
    text: str
    photos: List[str]
    is_verified_purchase: bool
    created_at: datetime

@app.get("/")
async def root():
    return {"service": "reviews-service", "status": "running"}


@app.get("/health")
async def health_check():
    """Basic health check - returns 200 if service is running"""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "service": "reviews-service"
    }


@app.get("/live")
async def liveness_check():
    """Liveness probe - checks if application is alive"""
    logger.info("Liveness check requested")
    return {
        "status": "alive",
        "service": "reviews-service",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/ready")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept requests"""
    logger.info("Readiness check requested")

    dependencies = {}
    all_healthy = True

    # Check Users Service
    users_status = await check_dependency(USERS_SERVICE_URL, "users-service")
    dependencies["users-service"] = users_status
    if users_status["status"] != "healthy":
        all_healthy = False

    # Check Products Service
    products_status = await check_dependency(PRODUCTS_SERVICE_URL, "products-service")
    dependencies["products-service"] = products_status
    if products_status["status"] != "healthy":
        all_healthy = False

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
        "service": "reviews-service",
        "timestamp": datetime.now().isoformat(),
        "dependencies": dependencies
    }

    if not all_healthy:
        raise HTTPException(status_code=503, detail=response)

    return response




async def check_dependency(url: str) -> Dict[str, Any]:
    start_time = time.time()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/health", timeout=2.0)
            response_time_ms = round((time.time() - start_time) * 1000, 2)
            if response.status_code == 200:
                return {"status": "healthy", "response_time_ms": response_time_ms}
            else:
                return {"status": "unhealthy", "status_code": response.status_code, "response_time_ms": response_time_ms}
    except Exception as e:
        response_time_ms = round((time.time() - start_time) * 1000, 2)
        return {"status": "unhealthy", "error": str(e), "response_time_ms": response_time_ms}


def calculate_storage_size():
    total_size = 0
    for review_dir in UPLOAD_DIR.iterdir():
        if review_dir.is_dir():
            for photo in review_dir.iterdir():
                if photo.is_file():
                    total_size += photo.stat().st_size
    photos_storage_size_bytes.set(total_size)
    return total_size


@app.post("/reviews", response_model=ReviewResponse)
async def create_review(
    user_id: int = Form(...),
    product_id: int = Form(...),
    order_id: int = Form(...),
    rating: int = Form(..., ge=1, le=5),
    text: str = Form(...),
    photos: List[UploadFile] = File(default=[])
):
    logger.info("Creating review", extra={"user_id": user_id, "product_id": product_id, "order_id": order_id, "rating": rating})

    if len(photos) > MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_PHOTOS} photos allowed")

    async with httpx.AsyncClient() as client:
        trace_id = get_trace_id()
        headers = {"X-Trace-ID": trace_id} if trace_id else {}

        # Verify user
        try:
            with HTTPClientMetrics("users-service", "GET") as metrics:
                user_response = await client.get(f"{USERS_SERVICE_URL}/users/{user_id}", headers=headers, timeout=5.0)
                metrics.set_status(user_response.status_code)
            if user_response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail="Users service unavailable")

        # Verify product
        try:
            with HTTPClientMetrics("products-service", "GET") as metrics:
                product_response = await client.get(f"{PRODUCTS_SERVICE_URL}/products/{product_id}", headers=headers, timeout=5.0)
                metrics.set_status(product_response.status_code)
            if product_response.status_code == 404:
                raise HTTPException(status_code=404, detail="Product not found")
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail="Products service unavailable")

        # Verify order
        try:
            with HTTPClientMetrics("orders-service", "GET") as metrics:
                order_response = await client.get(f"{ORDERS_SERVICE_URL}/orders/{order_id}", headers=headers, timeout=5.0)
                metrics.set_status(order_response.status_code)
            if order_response.status_code == 404:
                raise HTTPException(status_code=404, detail="Order not found")
            order_data = order_response.json()
            if order_data["user_id"] != user_id:
                raise HTTPException(status_code=403, detail="Order does not belong to this user")
            if order_data["status"] != "delivered":
                raise HTTPException(status_code=400, detail="Can only review delivered orders")
            if not any(item["product_id"] == product_id for item in order_data["items"]):
                raise HTTPException(status_code=400, detail="Product not found in this order")
            is_verified_purchase = True
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail="Orders service unavailable")

    # Process photos
    photo_filenames = []
    review_dir = UPLOAD_DIR / str(uuid.uuid4())
    review_dir.mkdir(parents=True, exist_ok=True)

    for photo in photos:
        ext = Path(photo.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Invalid file type")
        content = await photo.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large")
        try:
            image = Image.open(io.BytesIO(content))
            image.verify()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image file")
        filename = f"{uuid.uuid4()}{ext}"
        path = review_dir / filename
        async with aiofiles.open(path, 'wb') as f:
            await f.write(content)
        photo_filenames.append(filename)
        photos_uploaded_total.inc()

    # Insert review into DB
    with engine.connect() as conn:
        result = conn.execute(
            reviews.insert().values(
                user_id=user_id,
                product_id=product_id,
                order_id=order_id,
                rating=rating,
                text=text,
                photos=",".join(photo_filenames),
                is_verified_purchase=is_verified_purchase,
                created_at=datetime.utcnow()
            ).returning(reviews.c.id)
        )
        review_id = result.scalar()
        conn.commit()

    reviews_created_total.labels(rating=str(rating), verified_purchase=str(is_verified_purchase)).inc()
    if photo_filenames:
        reviews_with_photos_total.inc()

    # Update average rating
    with engine.connect() as conn:
        avg = conn.execute(select(func.avg(reviews.c.rating)).where(reviews.c.product_id == product_id)).scalar()
        average_product_rating.labels(product_id=str(product_id)).set(float(avg))

    calculate_storage_size()

    return ReviewResponse(
        id=review_id,
        user_id=user_id,
        product_id=product_id,
        order_id=order_id,
        rating=rating,
        text=text,
        photos=photo_filenames,
        is_verified_purchase=is_verified_purchase,
        created_at=datetime.utcnow()
    )


@app.get("/reviews", response_model=List[ReviewResponse])
async def get_reviews(
    product_id: Optional[int] = None,
    user_id: Optional[int] = None,
    sort: Optional[str] = "date",
    page: int = 1,
    limit: int = 10
):
    query = select(reviews)
    if product_id:
        query = query.where(reviews.c.product_id == product_id)
    if user_id:
        query = query.where(reviews.c.user_id == user_id)
    if sort == "rating":
        query = query.order_by(reviews.c.rating.desc())
    else:
        query = query.order_by(reviews.c.created_at.desc())
    offset = (page - 1) * limit
    query = query.limit(limit).offset(offset)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = [dict(row._mapping) for row in result]

    return [ReviewResponse(
        id=r["id"],
        user_id=r["user_id"],
        product_id=r["product_id"],
        order_id=r["order_id"],
        rating=r["rating"],
        text=r["text"],
        photos=r["photos"].split(",") if r["photos"] else [],
        is_verified_purchase=r["is_verified_purchase"],
        created_at=r["created_at"]
    ) for r in rows]


@app.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: int):
    query = select(reviews).where(reviews.c.id == review_id)
    with engine.connect() as conn:
        row = conn.execute(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    r = dict(row._mapping)
    return ReviewResponse(
        id=r["id"],
        user_id=r["user_id"],
        product_id=r["product_id"],
        order_id=r["order_id"],
        rating=r["rating"],
        text=r["text"],
        photos=r["photos"].split(",") if r["photos"] else [],
        is_verified_purchase=r["is_verified_purchase"],
        created_at=r["created_at"]
    )


@app.delete("/reviews/{review_id}")
async def delete_review(review_id: int):
    # Fetch review
    query = select(reviews).where(reviews.c.id == review_id)
    with engine.connect() as conn:
        row = conn.execute(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    r = dict(row._mapping)
    # Delete photos
    review_dirs = [d for d in UPLOAD_DIR.iterdir() if d.is_dir()]
    for d in review_dirs:
        for photo in r["photos"].split(","):
            path = d / photo
            if path.exists():
                path.unlink()
                photos_deleted_total.inc()
        if d.exists():
            d.rmdir()
    # Delete from DB
    with engine.connect() as conn:
        conn.execute(reviews.delete().where(reviews.c.id == review_id))
        conn.commit()
    reviews_deleted_total.inc()
    calculate_storage_size()
    # Update average rating
    with engine.connect() as conn:
        avg = conn.execute(select(func.avg(reviews.c.rating)).where(reviews.c.product_id == r["product_id"])).scalar()
        average_product_rating.labels(product_id=str(r["product_id"])).set(float(avg) if avg else 0)
    return {"message": "Review deleted successfully"}

@app.get("/products/{product_id}/reviews", response_model=List[ReviewResponse])
async def get_product_reviews(
    product_id: int,
    sort: Optional[str] = "date",
    page: int = 1,
    limit: int = 10
):
    """Get all reviews for a specific product"""
    query = select(reviews).where(reviews.c.product_id == product_id)
    if sort == "rating":
        query = query.order_by(reviews.c.rating.desc())
    else:
        query = query.order_by(reviews.c.created_at.desc())
    offset = (page - 1) * limit
    query = query.limit(limit).offset(offset)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = [dict(row._mapping) for row in result]

    return [ReviewResponse(
        id=r["id"],
        user_id=r["user_id"],
        product_id=r["product_id"],
        order_id=r["order_id"],
        rating=r["rating"],
        text=r["text"],
        photos=r["photos"].split(",") if r["photos"] else [],
        is_verified_purchase=r["is_verified_purchase"],
        created_at=r["created_at"]
    ) for r in rows]


@app.get("/products/{product_id}/rating")
async def get_product_rating(product_id: int):
    """Get rating statistics for a product"""
    with engine.connect() as conn:
        # Все отзывы продукта
        query = select(reviews).where(reviews.c.product_id == product_id)
        result = conn.execute(query)
        product_reviews = [dict(r._mapping) for r in result]

    if not product_reviews:
        return {
            "product_id": product_id,
            "average_rating": 0.0,
            "total_reviews": 0,
            "rating_distribution": {str(i): 0 for i in range(1, 6)},
            "verified_purchases": 0,
            "reviews_with_photos": 0
        }

    total_reviews = len(product_reviews)
    average_rating = sum(r["rating"] for r in product_reviews) / total_reviews

    # Распределение по оценкам
    rating_distribution = {str(i): 0 for i in range(1, 6)}
    for r in product_reviews:
        rating_distribution[str(r["rating"])] += 1

    verified_purchases = sum(1 for r in product_reviews if r["is_verified_purchase"])
    reviews_with_photos = sum(1 for r in product_reviews if r["photos"])

    return {
        "product_id": product_id,
        "average_rating": round(average_rating, 2),
        "total_reviews": total_reviews,
        "rating_distribution": rating_distribution,
        "verified_purchases": verified_purchases,
        "reviews_with_photos": reviews_with_photos
    }



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
