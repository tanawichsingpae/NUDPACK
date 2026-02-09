# server/app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

# --------------------------------------------------
# Database URL (from Render / Neon)
# --------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

def normalize_db_url(url: str) -> str:
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)

    if "sslmode=" not in url:
        joiner = "&" if "?" in url else "?"
        url = f"{url}{joiner}sslmode=require"

    return url


if DATABASE_URL:
    engine = create_engine(
        normalize_db_url(DATABASE_URL),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
else:
    # local dev fallback
    engine = create_engine(
        "sqlite:///./parcel.db",
        connect_args={"check_same_thread": False},
    )

# --------------------------------------------------
# Init DB + seed data
# --------------------------------------------------
def init_db():
    from server.app.models import CarrierList

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(CarrierList).count() == 0:
            carriers = [
                {"carrier_name": "FLASH Express", "logo": "/static/carriers/FLASH.jpg"},
                {"carrier_name": "J&T Express", "logo": "/static/carriers/J&T.jpg"},
                {"carrier_name": "SPX Express", "logo": "/static/carriers/SPX.jpg"},
                {"carrier_name": "DHL Express", "logo": "/static/carriers/DHL.jpg"},
                {"carrier_name": "KEX", "logo": "/static/carriers/KEX.jpg"},
                {"carrier_name": "Lazada eLogistics", "logo": "/static/carriers/LAZADA.jpg"},
            ]

            db.add_all(
                CarrierList(
                    carrier_name=c["carrier_name"],
                    logo=c["logo"],
                )
                for c in carriers
            )
            db.commit()
    finally:
        db.close()

# --------------------------------------------------
# Dependency
# --------------------------------------------------
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
