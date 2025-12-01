from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import uvicorn
import hashlib
import secrets
import httpx
import os
import time
from datetime import datetime

from dotenv import load_dotenv
from logger import logger, get_trace_id
from middleware import TraceIDMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from metrics import (
    users_registered_total,
    user_logins_total,
    user_logouts_total,
    active_users_gauge,
    start_metrics_updater,
    HTTPClientMetrics,
)
from sqlalchemy import select, insert

from database import async_session_maker, users, init_db, fetch_user_by_id, fetch_user_by_email

load_dotenv()

app = FastAPI(title="Users Service")

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
security = HTTPBearer()

# Initialize Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Configuration
ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders-service:8002")
PORT = int(os.getenv("PORT", "8003"))

# In-memory token store (sessions), users хранятся в PostgreSQL
tokens_db: Dict[str, int] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize DB and test user on startup."""
    logger.info("Initializing users database...")
    await init_db()
    logger.info("Users database initialized successfully")
    await init_test_user()


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str


class TokenResponse(BaseModel):
    token: str
    user: UserResponse


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token not in tokens_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    user_id = tokens_db[token]

    async with async_session_maker() as session:
        user = await fetch_user_by_id(session, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


async def init_test_user():
    """Initialize test user from environment variables if all are set (stored in DB)."""
    test_email = os.getenv("TEST_USER_EMAIL")
    test_password = os.getenv("TEST_USER_PASSWORD")
    test_name = os.getenv("TEST_USER_NAME")

    # Only create test user if all three variables are set
    if not all([test_email, test_password, test_name]):
        logger.info("Test user not configured (one or more env variables missing)")
        return

    async with async_session_maker() as session:
        existing = await fetch_user_by_email(session, test_email)
        if existing:
            logger.info(
                "Test user already exists",
                extra={"email": test_email}
            )
            return

        password_hash = hash_password(test_password)

        stmt = (
            insert(users)
            .values(
                email=test_email,
                name=test_name,
                password_hash=password_hash,
                created_at=datetime.utcnow(),
            )
            .returning(users.c.id)
        )
        result = await session.execute(stmt)
        user_id = result.scalar()
        await session.commit()

        # Update Prometheus metrics
        users_registered_total.inc()

        count_stmt = select(users.c.id)
        count_result = await session.execute(count_stmt)
        ids = [row[0] for row in count_result]
        active_users_gauge.set(len(ids))

    logger.info(
        "Test user created successfully",
        extra={
            "user_id": user_id,
            "email": test_email,
            "user_name": test_name,
        }
    )


@app.get("/")
async def root():
    return {"service": "users-service", "status": "running"}


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
        "service": "users-service"
    }


@app.get("/live")
async def liveness_check():
    """Liveness probe - checks if application is alive"""
    logger.info("Liveness check requested")
    return {
        "status": "alive",
        "service": "users-service",
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
        "service": "users-service",
        "timestamp": datetime.now().isoformat(),
        "dependencies": dependencies
    }

    if not all_healthy:
        raise HTTPException(status_code=503, detail=response)

    return response


@app.post("/register", response_model=TokenResponse)
async def register(user: UserRegister):
    logger.info("User registration attempt", extra={"email": user.email})

    async with async_session_maker() as session:
        # Check if email already exists
        existing = await fetch_user_by_email(session, user.email)
        if existing:
            logger.warning(
                "Registration failed - email already exists",
                extra={"email": user.email}
            )
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        password_hash = hash_password(user.password)

        stmt = (
            insert(users)
            .values(
                email=user.email,
                name=user.name,
                password_hash=password_hash,
                created_at=datetime.utcnow(),
            )
            .returning(users.c.id)
        )
        result = await session.execute(stmt)
        user_id = result.scalar()
        await session.commit()

        # Update Prometheus metrics
        users_registered_total.inc()

        count_stmt = select(users.c.id)
        count_result = await session.execute(count_stmt)
        ids = [row[0] for row in count_result]
        active_users_gauge.set(len(ids))

    token = generate_token()
    tokens_db[token] = user_id

    logger.info(
        "User registered successfully",
        extra={
            "user_id": user_id,
            "email": user.email,
            "user_name": user.name,
        }
    )

    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": user.email,
            "name": user.name
        }
    }


@app.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    logger.info("User login attempt", extra={"email": credentials.email})

    password_hash = hash_password(credentials.password)

    async with async_session_maker() as session:
        user = await fetch_user_by_email(session, credentials.email)

    if user and user["password_hash"] == password_hash:
        user_id = user["id"]
        token = generate_token()
        tokens_db[token] = user_id

        # Update Prometheus metrics
        user_logins_total.labels(result="success").inc()

        logger.info(
            "User logged in successfully",
            extra={
                "user_id": user_id,
                "email": user["email"],
            }
        )

        return {
            "token": token,
            "user": {
                "id": user_id,
                "email": user["email"],
                "name": user["name"]
            }
        }

    # Update Prometheus metrics for failed login
    user_logins_total.labels(result="failed").inc()

    logger.warning("Login failed - invalid credentials", extra={"email": credentials.email})

    raise HTTPException(
        status_code=401,
        detail="Invalid email or password"
    )


@app.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "name": current_user["name"]
    }


@app.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token in tokens_db:
        del tokens_db[token]
        # Update Prometheus metrics
        user_logouts_total.inc()
    return {"message": "Logged out successfully"}


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    logger.info("Fetching user", extra={"user_id": user_id})

    async with async_session_maker() as session:
        user = await fetch_user_by_id(session, user_id)

    if not user:
        logger.warning("User not found", extra={"user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(
        "User retrieved",
        extra={
            "user_id": user_id,
            "email": user["email"],
        }
    )

    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"]
    }


@app.get("/users/{user_id}/orders")
async def get_user_orders(user_id: int):
    logger.info("Fetching user orders", extra={"user_id": user_id})

    # Verify user exists
    async with async_session_maker() as session:
        user = await fetch_user_by_id(session, user_id)

    if not user:
        logger.warning("User orders failed - user not found", extra={"user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch orders from orders-service
    async with httpx.AsyncClient() as client:
        try:
            trace_id = get_trace_id()
            headers = {"X-Trace-ID": trace_id} if trace_id else {}

            logger.info(
                "Calling orders-service for user orders",
                extra={
                    "user_id": user_id,
                    "target_service": "orders-service",
                }
            )

            with HTTPClientMetrics("orders-service", "GET") as metrics:
                response = await client.get(
                    f"{ORDERS_SERVICE_URL}/orders",
                    params={"user_id": user_id},
                    headers=headers,
                    timeout=5.0
                )
                metrics.set_status(response.status_code)

            if response.status_code == 200:
                orders = response.json()

                logger.info(
                    "User orders retrieved",
                    extra={
                        "user_id": user_id,
                        "orders_count": len(orders),
                    }
                )

                return {
                    "user_id": user_id,
                    "user_name": user["name"],
                    "user_email": user["email"],
                    "orders_count": len(orders),
                    "orders": orders
                }
            else:
                logger.error(
                    "Failed to fetch user orders from orders-service",
                    extra={
                        "user_id": user_id,
                        "status_code": response.status_code,
                    }
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to fetch orders"
                )
        except httpx.RequestError as e:
            logger.error(
                "Orders service unavailable for user orders",
                extra={
                    "error": str(e),
                    "user_id": user_id,
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=503,
                detail="Orders service unavailable"
            )


@app.get("/users/{user_id}/stats")
async def get_user_stats(user_id: int):
    logger.info("Fetching user statistics", extra={"user_id": user_id})

    # Verify user exists
    async with async_session_maker() as session:
        user = await fetch_user_by_id(session, user_id)

    if not user:
        logger.warning("User stats failed - user not found", extra={"user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch orders from orders-service
    async with httpx.AsyncClient() as client:
        try:
            trace_id = get_trace_id()
            headers = {"X-Trace-ID": trace_id} if trace_id else {}

            logger.info(
                "Calling orders-service for user stats",
                extra={
                    "user_id": user_id,
                    "target_service": "orders-service",
                }
            )

            with HTTPClientMetrics("orders-service", "GET") as metrics:
                response = await client.get(
                    f"{ORDERS_SERVICE_URL}/orders",
                    params={"user_id": user_id},
                    headers=headers,
                    timeout=5.0
                )
                metrics.set_status(response.status_code)

            if response.status_code != 200:
                logger.error(
                    "Failed to fetch orders for user stats",
                    extra={
                        "user_id": user_id,
                        "status_code": response.status_code,
                    }
                )
                raise HTTPException(
                    status_code=503,
                    detail="Failed to fetch orders"
                )

            orders = response.json()

            if not orders:
                logger.info("User stats calculated - no orders", extra={"user_id": user_id})
                return {
                    "user_id": user_id,
                    "user_name": user["name"],
                    "user_email": user["email"],
                    "total_orders": 0,
                    "total_spent": 0.0,
                    "average_order_value": 0.0,
                    "orders_by_status": {},
                    "favorite_category": None,
                    "first_order_date": None,
                    "last_order_date": None
                }

            # Calculate statistics
            total_spent = 0.0
            orders_by_status = {}
            category_counts = {}
            first_order_date = None
            last_order_date = None

            for order in orders:
                # Count orders by status
                status = order["status"]
                orders_by_status[status] = orders_by_status.get(status, 0) + 1

                # Sum total spent (exclude cancelled orders)
                if status != "cancelled":
                    total_spent += order["total"]

                # Track order dates
                order_date = order["created_at"]
                if first_order_date is None or order_date < first_order_date:
                    first_order_date = order_date
                if last_order_date is None or order_date > last_order_date:
                    last_order_date = order_date

                # Note: We don't have category info in orders, would need to fetch from products
                # For now, skip favorite category calculation

            total_orders = len(orders)
            average_order_value = total_spent / total_orders if total_orders > 0 else 0.0

            logger.info(
                "User statistics calculated",
                extra={
                    "user_id": user_id,
                    "total_orders": total_orders,
                    "completed_orders": orders_by_status.get("delivered", 0),
                    "total_spent": round(total_spent, 2),
                }
            )

            return {
                "user_id": user_id,
                "user_name": user["name"],
                "user_email": user["email"],
                "total_orders": total_orders,
                "completed_orders": orders_by_status.get("delivered", 0),
                "cancelled_orders": orders_by_status.get("cancelled", 0),
                "total_spent": round(total_spent, 2),
                "average_order_value": round(average_order_value, 2),
                "orders_by_status": orders_by_status,
                "first_order_date": first_order_date,
                "last_order_date": last_order_date
            }

        except httpx.RequestError as e:
            logger.error(
                "Orders service unavailable for user stats",
                extra={
                    "error": str(e),
                    "user_id": user_id,
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=503,
                detail="Orders service unavailable"
            )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
