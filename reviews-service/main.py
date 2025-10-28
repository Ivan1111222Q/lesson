from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Response
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
app.add_middleware(TraceIDMiddleware)

# Initialize Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Configuration
USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://users-service:8003")
PRODUCTS_SERVICE_URL = os.getenv("PRODUCTS_SERVICE_URL", "http://products-service:8001")
ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders-service:8002")
PORT = int(os.getenv("PORT", "8004"))
UPLOAD_DIR = Path("/app/uploads")
MAX_PHOTOS = 5
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Ensure upload directory exists
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# In-memory database for demo
reviews_db = {}
review_id_counter = 1


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    order_id: int
    rating: int
    text: str
    photos: List[str]
    is_verified_purchase: bool
    created_at: str


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


def calculate_storage_size():
    """Calculate total storage size of uploaded photos"""
    total_size = 0
    for review_dir in UPLOAD_DIR.iterdir():
        if review_dir.is_dir():
            for photo in review_dir.iterdir():
                if photo.is_file():
                    total_size += photo.stat().st_size
    photos_storage_size_bytes.set(total_size)
    return total_size


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


@app.post("/reviews", response_model=ReviewResponse)
async def create_review(
    user_id: int = Form(...),
    product_id: int = Form(...),
    order_id: int = Form(...),
    rating: int = Form(..., ge=1, le=5),
    text: str = Form(...),
    photos: List[UploadFile] = File(default=[])
):
    """Create a new review with optional photos"""
    global review_id_counter

    logger.info(
        "Creating review",
        extra={
            "user_id": user_id,
            "product_id": product_id,
            "order_id": order_id,
            "rating": rating,
            "photos_count": len(photos)
        }
    )

    # Validate number of photos
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_PHOTOS} photos allowed"
        )

    # Check if user already reviewed this product
    for review in reviews_db.values():
        if review["user_id"] == user_id and review["product_id"] == product_id:
            logger.warning(
                "User already reviewed this product",
                extra={"user_id": user_id, "product_id": product_id}
            )
            raise HTTPException(
                status_code=400,
                detail="You have already reviewed this product"
            )

    async with httpx.AsyncClient() as client:
        trace_id = get_trace_id()
        headers = {"X-Trace-ID": trace_id} if trace_id else {}

        # Verify user exists
        logger.info("Verifying user exists", extra={"user_id": user_id})
        try:
            with HTTPClientMetrics("users-service", "GET") as metrics:
                user_response = await client.get(
                    f"{USERS_SERVICE_URL}/users/{user_id}",
                    headers=headers,
                    timeout=5.0
                )
                metrics.set_status(user_response.status_code)

            if user_response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
        except httpx.RequestError as e:
            logger.error("Users service unavailable", extra={"error": str(e)})
            raise HTTPException(status_code=503, detail="Users service unavailable")

        # Verify product exists
        logger.info("Verifying product exists", extra={"product_id": product_id})
        try:
            with HTTPClientMetrics("products-service", "GET") as metrics:
                product_response = await client.get(
                    f"{PRODUCTS_SERVICE_URL}/products/{product_id}",
                    headers=headers,
                    timeout=5.0
                )
                metrics.set_status(product_response.status_code)

            if product_response.status_code == 404:
                raise HTTPException(status_code=404, detail="Product not found")
        except httpx.RequestError as e:
            logger.error("Products service unavailable", extra={"error": str(e)})
            raise HTTPException(status_code=503, detail="Products service unavailable")

        # Verify order and purchase
        logger.info("Verifying purchase", extra={"order_id": order_id, "user_id": user_id})
        try:
            with HTTPClientMetrics("orders-service", "GET") as metrics:
                order_response = await client.get(
                    f"{ORDERS_SERVICE_URL}/orders/{order_id}",
                    headers=headers,
                    timeout=5.0
                )
                metrics.set_status(order_response.status_code)

            if order_response.status_code == 404:
                raise HTTPException(status_code=404, detail="Order not found")

            order_data = order_response.json()

            # Check if order belongs to user
            if order_data["user_id"] != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Order does not belong to this user"
                )

            # Check if order is delivered
            if order_data["status"] != "delivered":
                raise HTTPException(
                    status_code=400,
                    detail="Can only review delivered orders"
                )

            # Check if product is in order
            product_in_order = any(
                item["product_id"] == product_id for item in order_data["items"]
            )
            if not product_in_order:
                raise HTTPException(
                    status_code=400,
                    detail="Product not found in this order"
                )

            is_verified_purchase = True

        except httpx.RequestError as e:
            logger.error("Orders service unavailable", extra={"error": str(e)})
            raise HTTPException(status_code=503, detail="Orders service unavailable")

    # Process photos
    photo_filenames = []
    review_id = review_id_counter
    review_dir = UPLOAD_DIR / str(review_id)
    review_dir.mkdir(parents=True, exist_ok=True)

    for photo in photos:
        # Validate file extension
        file_ext = Path(photo.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Read file content
        content = await photo.read()

        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
            )

        # Validate it's a valid image
        try:
            image = Image.open(io.BytesIO(content))
            image.verify()
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid image file"
            )

        # Save file with UUID name
        photo_filename = f"{uuid.uuid4()}{file_ext}"
        photo_path = review_dir / photo_filename

        async with aiofiles.open(photo_path, 'wb') as f:
            await f.write(content)

        photo_filenames.append(photo_filename)
        photos_uploaded_total.inc()

        logger.info(
            "Photo uploaded",
            extra={
                "review_id": review_id,
                "photo_filename": photo_filename,
                "size": len(content)
            }
        )

    # Create review
    review_data = {
        "id": review_id,
        "user_id": user_id,
        "product_id": product_id,
        "order_id": order_id,
        "rating": rating,
        "text": text,
        "photos": photo_filenames,
        "is_verified_purchase": is_verified_purchase,
        "created_at": datetime.now().isoformat()
    }

    reviews_db[review_id] = review_data
    review_id_counter += 1

    # Update metrics
    reviews_created_total.labels(
        rating=str(rating),
        verified_purchase=str(is_verified_purchase)
    ).inc()

    if photo_filenames:
        reviews_with_photos_total.inc()

    # Update average rating for product
    product_reviews = [r for r in reviews_db.values() if r["product_id"] == product_id]
    avg_rating = sum(r["rating"] for r in product_reviews) / len(product_reviews)
    average_product_rating.labels(product_id=str(product_id)).set(avg_rating)

    # Update storage size
    calculate_storage_size()

    logger.info(
        "Review created successfully",
        extra={
            "review_id": review_id,
            "user_id": user_id,
            "product_id": product_id,
            "rating": rating,
            "photos_count": len(photo_filenames)
        }
    )

    return review_data


@app.get("/reviews", response_model=List[ReviewResponse])
async def get_reviews(
    product_id: Optional[int] = None,
    user_id: Optional[int] = None,
    sort: Optional[str] = "date",
    page: int = 1,
    limit: int = 10
):
    """Get all reviews with optional filtering and pagination"""
    logger.info(
        "Fetching reviews",
        extra={
            "product_id": product_id,
            "user_id": user_id,
            "sort": sort,
            "page": page,
            "limit": limit
        }
    )

    filtered_reviews = []
    for review_id, review in reviews_db.items():
        if product_id is not None and review["product_id"] != product_id:
            continue
        if user_id is not None and review["user_id"] != user_id:
            continue
        filtered_reviews.append(review)

    # Sort reviews
    if sort == "rating":
        filtered_reviews.sort(key=lambda x: x["rating"], reverse=True)
    else:  # date
        filtered_reviews.sort(key=lambda x: x["created_at"], reverse=True)

    # Pagination
    start = (page - 1) * limit
    end = start + limit
    paginated_reviews = filtered_reviews[start:end]

    logger.info(
        "Reviews retrieved",
        extra={
            "total_count": len(filtered_reviews),
            "returned_count": len(paginated_reviews)
        }
    )

    return paginated_reviews


@app.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: int):
    """Get a specific review"""
    logger.info("Fetching review", extra={"review_id": review_id})

    if review_id not in reviews_db:
        raise HTTPException(status_code=404, detail="Review not found")

    return reviews_db[review_id]


@app.delete("/reviews/{review_id}")
async def delete_review(review_id: int):
    """Delete a review and its photos"""
    logger.info("Deleting review", extra={"review_id": review_id})

    if review_id not in reviews_db:
        raise HTTPException(status_code=404, detail="Review not found")

    review = reviews_db[review_id]

    # Delete photos from disk
    review_dir = UPLOAD_DIR / str(review_id)
    if review_dir.exists():
        for photo_filename in review["photos"]:
            photo_path = review_dir / photo_filename
            if photo_path.exists():
                photo_path.unlink()
                photos_deleted_total.inc()
                logger.info(
                    "Photo deleted",
                    extra={"review_id": review_id, "filename": photo_filename}
                )

        # Remove directory
        review_dir.rmdir()

    # Delete review from database
    del reviews_db[review_id]

    # Update metrics
    reviews_deleted_total.inc()
    calculate_storage_size()

    # Update average rating for product
    product_id = review["product_id"]
    product_reviews = [r for r in reviews_db.values() if r["product_id"] == product_id]
    if product_reviews:
        avg_rating = sum(r["rating"] for r in product_reviews) / len(product_reviews)
        average_product_rating.labels(product_id=str(product_id)).set(avg_rating)
    else:
        average_product_rating.labels(product_id=str(product_id)).set(0)

    logger.info("Review deleted successfully", extra={"review_id": review_id})

    return {"message": "Review deleted successfully"}


@app.get("/reviews/{review_id}/photos/{photo_filename}")
async def get_photo(review_id: int, photo_filename: str):
    """Get a specific photo from a review"""
    logger.info(
        "Fetching photo",
        extra={"review_id": review_id, "filename": photo_filename}
    )

    if review_id not in reviews_db:
        raise HTTPException(status_code=404, detail="Review not found")

    review = reviews_db[review_id]
    if photo_filename not in review["photos"]:
        raise HTTPException(status_code=404, detail="Photo not found")

    photo_path = UPLOAD_DIR / str(review_id) / photo_filename

    if not photo_path.exists():
        logger.error(
            "Photo file not found on disk",
            extra={"review_id": review_id, "filename": photo_filename}
        )
        raise HTTPException(status_code=404, detail="Photo file not found")

    return FileResponse(
        photo_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"}
    )


@app.get("/products/{product_id}/reviews", response_model=List[ReviewResponse])
async def get_product_reviews(product_id: int):
    """Get all reviews for a specific product"""
    return await get_reviews(product_id=product_id, limit=1000)


@app.get("/products/{product_id}/rating")
async def get_product_rating(product_id: int):
    """Get rating statistics for a product"""
    logger.info("Fetching product rating", extra={"product_id": product_id})

    product_reviews = [r for r in reviews_db.values() if r["product_id"] == product_id]

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

    # Rating distribution
    rating_distribution = {str(i): 0 for i in range(1, 6)}
    for review in product_reviews:
        rating_distribution[str(review["rating"])] += 1

    verified_purchases = sum(1 for r in product_reviews if r["is_verified_purchase"])
    reviews_with_photos = sum(1 for r in product_reviews if r["photos"])

    result = {
        "product_id": product_id,
        "average_rating": round(average_rating, 2),
        "total_reviews": total_reviews,
        "rating_distribution": rating_distribution,
        "verified_purchases": verified_purchases,
        "reviews_with_photos": reviews_with_photos
    }

    logger.info(
        "Product rating retrieved",
        extra={
            "product_id": product_id,
            "average_rating": result["average_rating"],
            "total_reviews": total_reviews
        }
    )

    return result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
