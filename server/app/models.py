# server/app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .db import Base
from datetime import datetime, timezone, timedelta

def thai_now():
    return datetime.now(timezone(timedelta(hours=7)))

# พาร्सเซลหลัก
class Parcel(Base):
    __tablename__ = "parcels"
    id = Column(Integer, primary_key=True)
    tracking_number = Column(String, unique=True, index=True, nullable=False)

    carrier_id = Column(Integer, ForeignKey("carrier_list.carrier_id"), index=True)
    carrier = relationship("CarrierList")
    carrier_staff_name = Column(String)
    created_at = Column(DateTime(timezone=True), default=thai_now, index=True)

    queue_number = Column(String, index=True, nullable=True)
    status = Column(String, default="IN")
    recipient_name = Column(String, nullable=True)
    admin_staff_name = Column(String, nullable=True)
    picked_up_at = Column(DateTime(timezone=True), index=True, nullable=True)


# ตัวนับรายวัน (DailyCounter) — ใช้เก็บเลขลำดับต่อวันแยกตาม carrier
class DailyCounter(Base):
    __tablename__ = "daily_counters"
    id = Column(Integer, primary_key=True, autoincrement=True)

    carrier_id = Column(Integer, ForeignKey("carrier_list.carrier_id"), index=True)
    carrier = relationship("CarrierList")

    date = Column(String, index=True, nullable=False)  # YYYYMMDD

    created_at = Column(DateTime(timezone=True), default=thai_now)
    last_seq = Column(Integer, nullable=False, default=0)

# บันทึก audit
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    entity = Column(String)
    entity_id = Column(Integer)
    action = Column(String)
    user = Column(String)
    details = Column(Text)
    timestamp = Column(DateTime(timezone=True), default=thai_now)

# models.py
class RecycledQueue(Base):
    __tablename__ = "recycled_queues"

    id = Column(Integer, primary_key=True)

    carrier_id = Column(Integer, ForeignKey("carrier_list.carrier_id"), index=True)
    carrier = relationship("CarrierList")

    date = Column(String, index=True, nullable=False)  # YYYYMMDD
    queue_number = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=thai_now)

class CarrierList(Base):
    __tablename__ = "carrier_list"

    carrier_id = Column(Integer, primary_key=True)
    carrier_name = Column(String, index=True, nullable=False)
    logo = Column(String)

    parcels = relationship("Parcel", backref="carrier_obj")

