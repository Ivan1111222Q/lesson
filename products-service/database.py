import os
from datetime import datetime

from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Float,
    MetaData,
    DateTime,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)


POSTGRES_URL = (
    f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)


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

products = Table(
    "products",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String, nullable=False),
    Column("description", String, nullable=False),
    Column("price", Float, nullable=False),
    Column("stock", Integer, nullable=False),
    Column("category", String, nullable=False),
    Column("created_at", DateTime, default=datetime.utcnow),
)


async def init_db() -> None:
    """Create products table if it doesn't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)