# server/app/db.py
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import Generator

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # ParcelSystem/
DB_PATH = str(PROJECT_ROOT / "parcel.db")
SQLITE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    # import models so classes register to Base
    from server.app.models import CarrierList, QueueSection, Parcel  # 👈 เพิ่มทั้งหมดที่มี model

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # seed carrier_list (ถ้ายังไม่มีข้อมูล)
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
            CarrierList(carrier_name=c["carrier_name"], logo=c["logo"])
            for c in carriers
        ])

        db.commit()

    # 🔥 seed QueueSection ครั้งแรก
    if db.query(QueueSection).count() == 0:
        start = 1
        for i in range(30):
            end = start + 49
            db.add(QueueSection(
                start_seq=start,
                end_seq=end,
            ))
            start = end + 1

        db.commit()

    db.close()



def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()