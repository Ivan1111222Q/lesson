import os
import sqlalchemy
from sqlalchemy import Table, Column, Integer, String, MetaData, DateTime, Boolean
from datetime import datetime

POSTGRES_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)

engine = sqlalchemy.create_engine(POSTGRES_URL)
metadata = MetaData()

reviews = Table(
    "reviews",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False),
    Column("product_id", Integer, nullable=False),
    Column("order_id", Integer, nullable=False),
    Column("rating", Integer, nullable=False),
    Column("text", String, nullable=False),
    Column("photos", String, nullable=True),  # JSON строка, список фото
    Column("is_verified_purchase", Boolean, default=False),
    Column("created_at", DateTime, default=datetime.utcnow),
)

metadata.create_all(engine)
