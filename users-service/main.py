from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import uvicorn
import hashlib
import secrets
import httpx
import os
from dotenv import load_dotenv
from logger import logger, get_trace_id
from middleware import TraceIDMiddleware

load_dotenv()

app = FastAPI(title="Users Service")
app.add_middleware(TraceIDMiddleware)
security = HTTPBearer()

# Configuration
ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders-service:8002")
PORT = int(os.getenv("PORT", "8003"))

# In-memory database for demo
users_db = {}
tokens_db = {}
user_id_counter = 1


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


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token not in tokens_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    user_id = tokens_db[token]
    return users_db[user_id]


@app.get("/")
async def root():
    return {"service": "users-service", "status": "running"}


@app.post("/register", response_model=TokenResponse)
async def register(user: UserRegister):
    global user_id_counter

    logger.info("User registration attempt", extra={"email": user.email})

    # Check if email already exists
    for existing_user in users_db.values():
        if existing_user["email"] == user.email:
            logger.warning(
                "Registration failed - email already exists",
                extra={"email": user.email}
            )
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

    user_id = user_id_counter
    password_hash = hash_password(user.password)

    users_db[user_id] = {
        "id": user_id,
        "email": user.email,
        "name": user.name,
        "password_hash": password_hash
    }

    token = generate_token()
    tokens_db[token] = user_id
    user_id_counter += 1

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

    for user_id, user in users_db.items():
        if (user["email"] == credentials.email and
                user["password_hash"] == password_hash):
            token = generate_token()
            tokens_db[token] = user_id

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
    return {"message": "Logged out successfully"}


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    logger.info("Fetching user", extra={"user_id": user_id})

    if user_id not in users_db:
        logger.warning("User not found", extra={"user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")

    user = users_db[user_id]

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
    if user_id not in users_db:
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

            response = await client.get(
                f"{ORDERS_SERVICE_URL}/orders",
                params={"user_id": user_id},
                headers=headers,
                timeout=5.0
            )
            if response.status_code == 200:
                orders = response.json()
                user = users_db[user_id]

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
    if user_id not in users_db:
        logger.warning("User stats failed - user not found", extra={"user_id": user_id})
        raise HTTPException(status_code=404, detail="User not found")

    user = users_db[user_id]

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

            response = await client.get(
                f"{ORDERS_SERVICE_URL}/orders",
                params={"user_id": user_id},
                headers=headers,
                timeout=5.0
            )
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
