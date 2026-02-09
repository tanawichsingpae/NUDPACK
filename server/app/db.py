# server/app/db.py
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# --------------------------------------------------
# Database URL (from Render / Neon)
# --------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

def normalize_db_url(url: str) -> str:
    url = url.strip()

    # 🔎 debug (ดูใน Render log)
    print("RAW DATABASE_URL =", repr(url))

    # Neon / Heroku style
    if url.startswith("postgres://"):
        url = url.replace(
            "postgres://",
            "postgresql+psycopg2://",
            1
        )

    # force ssl (Neon ต้องใช้)
    if "sslmode=" not in url:
        joiner = "&" if "?" in url else "?"
        url = f"{url}{joiner}sslmode=require"

    print("NORMALIZED DATABASE_URL =", url)
    return url


if DATABASE_URL:
    engine = create_engine(
        normalize_db_url(DATABASE_URL),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
else:
    # local dev fallback (สำคัญมาก)
    engine = create_engine(
        "sqlite:///./parcel.db",
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

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
