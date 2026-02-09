# server/app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

# --------------------------------------------------
# Database URL (from Render / Neon)
# --------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# --------------------------------------------------
# SQLAlchemy engine
# --------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,     # ป้องกัน connection ตาย
    pool_size=5,
    max_overflow=10,
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
