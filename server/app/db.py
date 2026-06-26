# server/app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

# --------------------------------------------------
# Database URL (from Railway / Render / Neon)
# --------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

def normalize_db_url(url: str) -> str:
    url = url.strip()

    # debug log (ดูใน Railway log ได้)
    print("RAW DATABASE_URL =", repr(url))

    # กรณี Neon / Heroku ใช้ postgres://
    if url.startswith("postgres://"):
        url = url.replace(
            "postgres://",
            "postgresql+psycopg2://",
            1
        )

    return url

DATABASE_URL = normalize_db_url(DATABASE_URL)

# --------------------------------------------------
# Engine (PostgreSQL)
# --------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,     # ป้องกัน connection ตาย
    pool_recycle=300
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# --------------------------------------------------
# Initialize Database
# --------------------------------------------------
def init_db():
    from server.app.models import CarrierList, QueueSection, Parcel

    # create tables (ครั้งแรกเท่านั้น)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # -----------------------------
        # Seed carrier_list
        # -----------------------------
        if db.query(CarrierList).count() == 0:
            carriers = [
                {"carrier_name": "FLASH Express", "logo": "/static/carriers/FLASH.jpg"},
                {"carrier_name": "J&T Express", "logo": "/static/carriers/J&T.jpg"},
                {"carrier_name": "SPX Express", "logo": "/static/carriers/SPX.jpg"},
                {"carrier_name": "DHL Express", "logo": "/static/carriers/DHL.jpg"},
                {"carrier_name": "KEX", "logo": "/static/carriers/KEX.jpg"},
                {"carrier_name": "Lazada eLogistics", "logo": "/static/carriers/LAZADA.jpg"},
            ]

            db.add_all([
                CarrierList(
                    carrier_name=c["carrier_name"],
                    logo=c["logo"]
                )
                for c in carriers
            ])
            db.commit()

        # -----------------------------
        # Seed QueueSection
        # -----------------------------
        if db.query(QueueSection).count() == 0:
            start = 1
            for _ in range(20):
                end = start + 49
                db.add(QueueSection(
                    start_seq=start,
                    end_seq=end,
                ))
                start = end + 1

            db.commit()

    finally:
        db.close()

# --------------------------------------------------
# Dependency (FastAPI)
# --------------------------------------------------
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
