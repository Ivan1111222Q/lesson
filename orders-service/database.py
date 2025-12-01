import os
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Float,
    MetaData,
    DateTime,
    JSON,
    select,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)


def _build_postgres_url() -> str:
    """
    Build PostgreSQL connection URL from environment variables.

    Делает URL устойчивым к странным значениям PORT вида 'tcp://5432':
    берём только цифры, по умолчанию 5432.
    """
    user = os.getenv("POSTGRES_USER", "user")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    host = os.getenv("POSTGRES_HOST", "postgres")
    raw_port = os.getenv("POSTGRES_PORT", "5432")

    digits = "".join(ch for ch in raw_port if ch.isdigit())
    port = digits or "5432"

    db = os.getenv("POSTGRES_DB", "reviews")

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


POSTGRES_URL = _build_postgres_url()

engine = create_async_engine(
    POSTGRES_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

metadata = MetaData()

orders = Table(
    "orders",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("items", JSON, nullable=False),  # список позиций заказа
    Column("status", String, nullable=False, default="pending"),
    Column("total", Float, nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow),
)


async def init_db() -> None:
    """Create orders table if it doesn't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def fetch_order(session: AsyncSession, order_id: int) -> Dict[str, Any] | None:
    """Получить один заказ из БД как словарь или None."""
    stmt = select(orders).where(orders.c.id == order_id)
    result = await session.execute(stmt)
    row = result.first()
    return dict(row._mapping) if row else None

