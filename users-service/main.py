from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import uvicorn
import hashlib
import secrets
import httpx

app = FastAPI(title="Users Service")
security = HTTPBearer()

# Configuration
ORDERS_SERVICE_URL = "http://orders-service:8002"

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

    # Check if email already exists
    for existing_user in users_db.values():
        if existing_user["email"] == user.email:
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
    password_hash = hash_password(credentials.password)

    for user_id, user in users_db.items():
        if (user["email"] == credentials.email and
                user["password_hash"] == password_hash):
            token = generate_token()
            tokens_db[token] = user_id
            return {
                "token": token,
                "user": {
                    "id": user_id,
                    "email": user["email"],
                    "name": user["name"]
                }
            }

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
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    user = users_db[user_id]
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"]
    }


@app.get("/users/{user_id}/orders")
async def get_user_orders(user_id: int):
    # Verify user exists
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch orders from orders-service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{ORDERS_SERVICE_URL}/orders",
                params={"user_id": user_id},
                timeout=5.0
            )
            if response.status_code == 200:
                orders = response.json()
                user = users_db[user_id]
                return {
                    "user_id": user_id,
                    "user_name": user["name"],
                    "user_email": user["email"],
                    "orders_count": len(orders),
                    "orders": orders
                }
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Failed to fetch orders"
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Orders service unavailable"
            )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
