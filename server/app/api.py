# server/app/api.py
from fileinput import filename
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Response, Request, Header, Depends,Form
from fastapi.responses import RedirectResponse,FileResponse, JSONResponse
from pydantic import BaseModel
from .db import SessionLocal, init_db
from .models import Parcel, DailyCounter, AuditLog, RecycledQueue,CarrierList,QueueSection,User

from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_
import io, csv
from starlette.middleware.sessions import SessionMiddleware
from .models import thai_now
from datetime import datetime, timedelta , timezone
from pathlib import Path
from .admin_auth import require_admin, verify_admin_password
from urllib.parse import quote
from sqlalchemy.orm import Session

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except Exception:
    PANDAS_AVAILABLE = False

import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import Request, Form
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware


app = FastAPI(title="ParcelServer API")


from fastapi.middleware.cors import CORSMiddleware
BASE_DIR = Path(__file__).resolve().parent
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "parcel-session-secret")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def write_audit(db, *, entity, entity_id, action, user, details):
    log = AuditLog(
        entity=entity,
        entity_id=entity_id,
        action=action,
        user=user,
        details=details
    )
    db.add(log)

from sqlalchemy import func

def normalize_tracking_column(column):
    """
    ทำให้ tracking ใน DB:
    - ตัด space
    - ไม่สนตัวเล็กใหญ่
    """
    return func.replace(
        func.lower(column),
        " ",
        ""
    )

def normalize_tracking_value(value: str):
    return value.strip().replace(" ", "").lower()


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    same_site="none",
    https_only=True
)


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost:8000",
        "https://127.0.0.1:8000",
        "https://192.168.249.105:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- resolve project and static directories ---
# file is server/app/api.py -> parents[2] => project root (ParcelSystem)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIENT_STATIC = PROJECT_ROOT / "client" / "static"
SERVER_STATIC = PROJECT_ROOT / "server" / "static"


# Mount client static at /static (client UI)
if CLIENT_STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(CLIENT_STATIC)), name="static")

# Also mount server static under /admin_static for admin assets (optional)
if SERVER_STATIC.exists():
    app.mount("/admin_static", StaticFiles(directory=str(SERVER_STATIC)), name="admin_static")


@app.get("/client")
def client_ui(request: Request):

    if not request.session.get("carrier_id"):
        return RedirectResponse("/login_client")

    return FileResponse(str(CLIENT_STATIC / "client.html"))

@app.get("/login_client")
def login_page():
    return FileResponse(str(CLIENT_STATIC / "login_client.html"))

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    response = RedirectResponse("/login_client", status_code=302)

    # กัน cache
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return response

@app.get("/admin/login")
def admin_login_page():
    return RedirectResponse("/login_admin", status_code=302)

@app.get("/login_admin")
def login_admin_alias(request: Request):
    request.session.clear()   # 👈 ตัด session admin ทิ้งทุกครั้ง
    return FileResponse(str(CLIENT_STATIC / "login_admin.html"))

@app.get("/admin/logout")
def admin_logout(request: Request):

    request.session.clear()   # 👈 สำคัญสุด

    response = RedirectResponse("/login_admin", status_code=302)

    # กัน cache
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return response

@app.get("/recipient/login")
def recipient_login_page():
    return RedirectResponse("/login_recipient", status_code=302)

@app.get("/login_recipient")
def login_recipient_alias(request: Request):
    request.session.clear()   # 👈 ตัด session admin ทิ้งทุกครั้ง
    return FileResponse(str(CLIENT_STATIC / "login_recipient.html"))

@app.get("/recipient/logout")
def recipient_logout(request: Request):

    request.session.clear()   # 👈 สำคัญสุด

    response = RedirectResponse("/login_recipient", status_code=302)

    # กัน cache
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return response


class AdminLoginIn(BaseModel):
    name: str
    password: str


@app.post("/admin/login")
def admin_login(payload: AdminLoginIn, request: Request):

    if not verify_admin_password(payload.password):
        raise HTTPException(status_code=401, detail="รหัสผ่านไม่ถูกต้อง")

    request.session["admin"] = {
        "name": payload.name
    }

    return {"ok": True, "name": payload.name}


@app.get("/admin")
def admin_ui(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse("/login_admin")

    server_admin = SERVER_STATIC / "admin.html"
    if server_admin.exists():
        return FileResponse(str(server_admin))

    client_admin = CLIENT_STATIC / "admin.html"
    if client_admin.exists():
        return FileResponse(str(client_admin))

    raise HTTPException(status_code=404, detail="admin.html not found")

class RecipientLoginIn(BaseModel):
    name: str

@app.post("/recipient/login")
def recipient_login(payload: RecipientLoginIn, request: Request):

    request.session["recipient"] = {
        "name": payload.name
    }

    return {"ok": True, "name": payload.name}


@app.get("/recipient")
def recipient_ui(request: Request):
    if not request.session.get("recipient"):
        return RedirectResponse("/login_recipient")

    server_recipient = SERVER_STATIC / "recipient.html"
    if server_recipient.exists():
        return FileResponse(str(server_recipient))

    client_recipient = CLIENT_STATIC / "recipient.html"
    if client_recipient.exists():
        return FileResponse(str(client_recipient))

    raise HTTPException(status_code=404, detail="recipient.html not found")

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.get("/audit")
def audit_page(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse("/login_admin")

    return templates.TemplateResponse(
        "audit.html",
        {"request": request}
    )
# Startup: init DB
@app.on_event("startup")
def on_startup():
    init_db()

class LoginIn(BaseModel):
    carrier_id: int
    carrier_staff_name: str

@app.post("/api/login_client")
def login(
    payload: LoginIn,
    request: Request,
    db: Session = Depends(get_db)
):
    # 🔎 หา user เดิม
    user = db.query(User).filter(
        User.name == payload.carrier_staff_name
    ).first()

    # ❗ ถ้าไม่มี → สร้างใหม่
    if not user:
        user = User(name=payload.carrier_staff_name)
        db.add(user)
        db.commit()
        db.refresh(user)

    # ✅ เก็บ session
    request.session["carrier_id"] = payload.carrier_id
    request.session["carrier_staff_name"] = payload.carrier_staff_name
    request.session["user_id"] = user.id   # ⭐ สำคัญมาก

    return {"ok": True}


# Pydantic input model
class ParcelIn(BaseModel):
    tracking_number: str
    recipient_name: Optional[str] = None
    unofficial_recipient: Optional[str] = None # 👈 เพิ่ม
    admin_staff_name: Optional[str] = None
    provisional: bool = False
    section_id: int


class ConfirmPickupIn(BaseModel):
    recipient_name: Optional[str] = None
    scanner_id: Optional[str] = None

class BulkDeleteIn(BaseModel):
    ids: Optional[list[int]] = None
    trackings: Optional[list[str]] = None


# ---------------------------
# Create parcel (check-in / provisional)
# ---------------------------
from sqlalchemy import cast, Integer
@app.post("/api/parcels")
def create_parcel(p: ParcelIn, request: Request):
    db = SessionLocal()
    try:
        carrier_id = request.session.get("carrier_id")
        carrier_staff = request.session.get("carrier_staff_name")
        user_id = request.session.get("user_id")


        if not carrier_id:
            raise HTTPException(401, "not logged in")

        tracking_clean = normalize_tracking_value(p.tracking_number)

        existing = db.query(Parcel).filter(
            normalize_tracking_column(Parcel.tracking_number) == tracking_clean
        ).first()

        if existing:
            raise HTTPException(409, "พัสดุชิ้นนี้แสกนแล้ว")

        # 🔥 lock section ที่เลือก
        # 🔥 หา reservation ที่ยัง active ของ carrier
        today = thai_now().strftime("%Y%m%d")

        # 🔥 ดึง reservation ทั้งหมดของ carrier วันนี้
        reservations = (
            db.query(QueueReservation)
            .filter(
                QueueReservation.date == today,
                QueueReservation.user_id == user_id,
                QueueReservation.status == "active"
            )
            .order_by(QueueReservation.start_seq.asc())
            .with_for_update()
            .all()
        )

        if not reservations:
            raise HTTPException(400, "ยังไม่มีคิวที่จองไว้")

        # 🔥 หา reservation แรกที่ยังไม่เต็ม (เรียงตาม start_seq แล้ว)

        current_reservation = None

        for r in reservations:
            if r.current_seq < r.end_seq:
                current_reservation = r
                break

        if not current_reservation:
            raise HTTPException(400, "คิวเต็มทุก section แล้ว")


        next_queue = current_reservation.current_seq + 1
        current_reservation.current_seq = next_queue
        queue_number = str(next_queue)
                
        # ❌ ห้าม set full ที่นี่
        current_reservation.status = "active"

        carrier = db.query(CarrierList).filter(
            CarrierList.carrier_id == carrier_id   # ✅ ใช้จาก session
        ).first()
        carrier_name = carrier.carrier_name if carrier else "Unknown"
        status = "กำลังรอ" if p.provisional else "ยังไม่ได้รับ"
        parcel = Parcel(
            tracking_number=p.tracking_number,
            carrier_id=carrier_id,
            carrier_staff_name=carrier_staff,
            queue_number=queue_number,
            recipient_name=p.recipient_name,
            unofficial_recipient=p.unofficial_recipient, # 👈 เพิ่ม
            admin_staff_name=p.admin_staff_name,
            status=status,
            section_id=current_reservation.section_id


        )

        db.add(parcel)
        db.commit()
        db.refresh(parcel)

        write_audit(
            db,
            entity="พัสดุ",
            entity_id=parcel.id,
            action="เพิ่มหมายเลขพัสดุ",
            user=f"พนักงานขนส่ง {carrier_name}: {carrier_staff}",
            details=(
                    f"หมายเลขพัสดุ: {p.tracking_number}"
                    f"\nเลขคิว: {parcel.queue_number}"
                    + (f"\nชื่อหน้ากล่อง: {p.unofficial_recipient}"
                    if p.unofficial_recipient else "")
                ),
        )
        db.commit()

        return {
            "id": parcel.id,
            "queue_number": parcel.queue_number,
            "status": parcel.status,
            "section_id": current_reservation.section_id


        }

    finally:
        db.close()




# ---------------------------
# Confirm pending -> RECEIVED
# ---------------------------
@app.post("/api/parcels/{tracking}/confirm_pending")
def confirm_pending(tracking: str, request: Request):
    db = SessionLocal()
    try:
        carrier_staff = request.session.get("carrier_staff_name")
        
        tracking_clean = normalize_tracking_value(tracking)

        p = db.query(Parcel).filter(
            normalize_tracking_column(Parcel.tracking_number) == tracking_clean
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="parcel not found")
        if p.status != "กำลังรอ":
            return {"ok": False, "message": "parcel not pending"}
        
        carrier = db.query(CarrierList).filter(
            CarrierList.carrier_id == p.carrier_id
        ).first()

        carrier_name = carrier.carrier_name if carrier else "Unknown"
        
        p.status = "ยังไม่ได้รับ"
                # 🔥 เปิด section ให้จองได้ (เปลี่ยนเป็นเขียว)
        today = thai_now().strftime("%Y%m%d")

        active_reservations = db.query(QueueReservation).filter(
            QueueReservation.carrier_id == p.carrier_id,
            QueueReservation.user_id == request.session.get("user_id"),
            QueueReservation.date == today,
            QueueReservation.status == "active"
        ).all()

        for reservation in active_reservations:

            # ถ้า section นี้มี parcel ใช้งานจริง
            if reservation.section_id == p.section_id:

                if reservation.current_seq >= reservation.end_seq:
                    reservation.status = "full"
                else:
                    reservation.status = "unactive"

            else:
                # 🔥 section ที่ไม่ได้ใช้เลย
                reservation.status = "unactive"



        db.add(p)
        db.commit()
        db.refresh(p)

        write_audit(
            db,
            entity="พัสดุ", 
            entity_id=p.id, 
            action="ยืนยันการเพิ่มหมายเลขพัสดุ", 
            user=f"พนักงานขนส่ง {carrier_name}: {carrier_staff}",
            details=(
                    f"หมายเลขพัสดุ: {p.tracking_number}"
                    f"\nเลขคิว: {p.queue_number}"
                    + (f"\nชื่อหน้ากล่อง: {p.unofficial_recipient}"
                    if p.unofficial_recipient else "")
                ),
        )
        db.commit()

        return {
            "ok": True,
            "tracking": p.tracking_number,
            "queue_number": p.queue_number
        }

    finally:
        db.close()

@app.get("/api/parcels/search")
def search_parcels(
    q: str | None = None,
    date: str | None = None,
    admin = Depends(require_admin)
):
    db = SessionLocal()

    try:
        query = db.query(Parcel)

        # ---------- queue filter ----------
        if q:
            query = query.filter(Parcel.queue_number.ilike(f"%{q}%"))

        # ---------- date filter ----------
        if date:
            day = datetime.strptime(date, "%Y-%m-%d")
            start = day.replace(hour=0, minute=0, second=0, microsecond=0,
                                tzinfo=timezone(timedelta(hours=7)))
            end = start + timedelta(days=1)

            query = query.filter(
                and_(
                    Parcel.created_at >= start,
                    Parcel.created_at < end
                )
            )

        parcels = query.order_by(Parcel.created_at.desc()).all()

        return {
            "count": len(parcels),
            "items": [
                {
                    "tracking_number": p.tracking_number,
                    "queue_number": p.queue_number,
                    "status": p.status,
                    "recipient_name": p.recipient_name,
                    "admin_staff_name": p.admin_staff_name,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "picked_up_at": p.picked_up_at.isoformat() if p.picked_up_at else None,
                }
                for p in parcels
            ]
        }

    finally:
        db.close()

# ---------------------------
# Get single parcel
# ---------------------------
@app.get("/api/parcels/{tracking}")
def get_parcel(tracking: str):
    db = SessionLocal()
    try:
        tracking_clean = normalize_tracking_value(tracking)

        p = db.query(Parcel).filter(
            normalize_tracking_column(Parcel.tracking_number)
            == tracking_clean
        ).first()

        if not p:
            raise HTTPException(status_code=404, detail="not found")
        return {
            "id": p.id,
            "tracking_number": p.tracking_number,
            "queue_number": p.queue_number,
            "status": p.status,
            "recipient_name": p.recipient_name,
            "admin_staff_name": p.admin_staff_name,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "picked_up_at": p.picked_up_at.isoformat() if p.picked_up_at else None
        }
    finally:
        db.close()

# ---------------------------
# Pickup (confirm) endpoint (simple)
# ---------------------------
@app.post("/api/parcels/{tracking}/pickup")
def pickup_parcel(
    tracking: str,
    payload: ConfirmPickupIn,
    request: Request
):
    recipient = request.session.get("recipient")
    if not recipient:
        raise HTTPException(401, "not logged in")

    db = SessionLocal()
    try:
        tracking_clean = normalize_tracking_value(tracking)

        p = db.query(Parcel).filter(
            normalize_tracking_column(Parcel.tracking_number)
            == tracking_clean
        ).first()

        if not p:
            raise HTTPException(404, "parcel not found")

        if p.status == "ได้รับแล้ว":
            return {"ok": True, "message": "รับไปแล้ว"}

        if not payload.recipient_name or not payload.recipient_name.strip():
            raise HTTPException(400, "ต้องกรอกชื่อผู้รับ")

        p.status = "ได้รับแล้ว"
        p.recipient_name = payload.recipient_name
        p.picked_up_at = thai_now()

        db.commit()
        db.refresh(p)
        write_audit(
            db,
            entity="พัสดุ",
            entity_id=p.id,
            action="ได้รับพัสดุ",
            user=f"ผู้รับ: {recipient['name']}",
            details=(
                    f"หมายเลขพัสดุ: {p.tracking_number}"
                    f"\nเลขคิว: {p.queue_number}"
                    + (f"\nชื่อหน้ากล่อง: {p.unofficial_recipient}"
                    if p.unofficial_recipient else "")
                ),
        )
        db.commit()

        return {"ok": True}
    finally:
        db.close()

# ---------------------------
# List recent parcels
# ---------------------------
@app.get("/api/recipient/parcels")
def recipient_list_parcels(
    limit: int = 500,
    status: Optional[str] = Query(None),
    date: Optional[str] = Query(None),   # "today" | "YYYY-MM-DD" | None
    queue: Optional[str] = Query(None),
    recipient: Optional[str] = Query(None)
):
    db = SessionLocal()
    try:
        q = db.query(Parcel)

        # ================= STATUS FILTER =================
        if status and status != "ทั้งหมด":
            q = q.filter(Parcel.status == status)
        # ================= REQUIRE CONDITION =================
        if date and not queue and not recipient:
            raise HTTPException(
                status_code=400,
                detail="ไม่สามารถค้นหาด้วยวันที่อย่างเดียวได้ กรุณาระบุเลขคิวหรือชื่อผู้รับด้วย"
            )

        # ================= DATE FILTER =================
        if date and date != "all":

            if date == "today":
                d = thai_now()

            else:
                d = None

                # ลอง yyyy-mm-dd ก่อน
                try:
                    d = datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    pass

                # ถ้าไม่ใช่ → ลอง dd/mm/yyyy
                if not d:
                    try:
                        d = datetime.strptime(date, "%d/%m/%Y")
                    except ValueError:
                        pass

            if d:
                start = d.replace(hour=0, minute=0, second=0, microsecond=0,
                                  tzinfo=timezone(timedelta(hours=7)))
                end = start + timedelta(days=1)

                q = q.filter(
                    Parcel.created_at >= start,
                    Parcel.created_at < end
                )
# ================= QUEUE + RECIPIENT FILTER =================
            if queue or recipient:

                conditions = []

                if queue:
                    conditions.append(
                        Parcel.queue_number.ilike(f"%{queue}%")
                    )

                if recipient:
                    recipient_clean = normalize_tracking_value(recipient)

                    conditions.append(
                        or_(
                            normalize_tracking_column(Parcel.recipient_name).like(f"%{recipient_clean}%"),
                            normalize_tracking_column(Parcel.unofficial_recipient).like(f"%{recipient_clean}%"),
                        )
                    )

                q = q.filter(or_(*conditions))
        rows = (
            q.order_by(Parcel.created_at.asc())
             .limit(limit)
             .all()
        )

        out = []
        for p in rows:
            out.append({
                "id": p.id,
                "tracking_number": p.tracking_number,
                "queue_number": p.queue_number,
                "status": p.status,
                "recipient_name": p.recipient_name,
                "unofficial_recipient": p.unofficial_recipient,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "picked_up_at": p.picked_up_at.isoformat() if p.picked_up_at else None
            })

        return out

    finally:
        db.close()

# ---------------------------
# Search parcels (tracking or queue)
# ---------------------------


# ---------------------------
# List recent parcels
# ---------------------------
@app.get("/api/parcels")
def list_parcels(
    limit: int = 500,
    status: Optional[str] = Query(None),
    date: Optional[str] = Query(None),   # "today" | "YYYY-MM-DD" | None
    queue: Optional[str] = Query(None),
    recipient: Optional[str] = Query(None),
    admin = Depends(require_admin)
):
    db = SessionLocal()
    try:
        q = db.query(Parcel)

        # ================= STATUS FILTER =================
        if status and status != "ทั้งหมด":
            q = q.filter(Parcel.status == status)

        # ================= DATE FILTER =================
        if date and date != "all":

            if date == "today":
                d = thai_now()

            else:
                d = None

                # ลอง yyyy-mm-dd ก่อน
                try:
                    d = datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    pass

                # ถ้าไม่ใช่ → ลอง dd/mm/yyyy
                if not d:
                    try:
                        d = datetime.strptime(date, "%d/%m/%Y")
                    except ValueError:
                        pass

            if d:
                start = d.replace(hour=0, minute=0, second=0, microsecond=0,
                                  tzinfo=timezone(timedelta(hours=7)))
                end = start + timedelta(days=1)

                q = q.filter(
                    Parcel.created_at >= start,
                    Parcel.created_at < end
                )
# ================= QUEUE + RECIPIENT FILTER =================
            if queue or recipient:

                conditions = []

                if queue:
                    conditions.append(
                        Parcel.queue_number.ilike(f"%{queue}%")
                    )

                if recipient:
                    like = f"%{recipient}%"
                    conditions.append(
                        or_(
                            Parcel.recipient_name.ilike(like),
                            Parcel.unofficial_recipient.ilike(like),
                        )
                    )

                q = q.filter(or_(*conditions))

        rows = (
            q.order_by(Parcel.created_at.asc())
             .limit(limit)
             .all()
        )

        out = []
        for p in rows:
            out.append({
                "id": p.id,
                "tracking_number": p.tracking_number,
                "queue_number": p.queue_number,
                "status": p.status,
                "recipient_name": p.recipient_name,
                "unofficial_recipient": p.unofficial_recipient,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "picked_up_at": p.picked_up_at.isoformat() if p.picked_up_at else None
            })

        return out

    finally:
        db.close()


# ---------------------------
# Two-step checkout endpoints for UI double-scan
# ---------------------------

from sqlalchemy import func

@app.post("/api/parcels/{tracking}/verify")
def verify_parcel(tracking: str):
    db = SessionLocal()
    try:
        tracking_clean = normalize_tracking_value(tracking)

        p = db.query(Parcel).filter(
            normalize_tracking_column(Parcel.tracking_number)
            == tracking_clean
        ).first()

        if not p:
            raise HTTPException(status_code=404, detail="parcel not found")

        return {
            "tracking": p.tracking_number,
            "queue_number": p.queue_number,
            "recipient_name": p.recipient_name,
            "admin_staff_name": p.admin_staff_name,
            "status": p.status,
            "picked_up_at": p.picked_up_at.isoformat() if p.picked_up_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
    finally:
        db.close()

from .models import AuditLog
@app.post("/api/parcels/{tracking}/confirm_pickup")
def confirm_pickup(
    tracking: str,
    payload: ConfirmPickupIn,
    admin = Depends(require_admin)
):
    db = SessionLocal()
    try:
        tracking_clean = normalize_tracking_value(tracking)

        p = db.query(Parcel).filter(
            normalize_tracking_column(Parcel.tracking_number)
            == tracking_clean
        ).first()

        if not p:
            raise HTTPException(status_code=404, detail="parcel not found")

        if not payload.recipient_name or not payload.recipient_name.strip():
            raise HTTPException(
                status_code=400,
                detail="ต้องกรอกชื่อผู้รับก่อนยืนยันรับพัสดุ"
            )

        # -----------------------------
        # กรณีรับไปแล้ว
        # -----------------------------
        if p.picked_up_at:
            p.recipient_name = payload.recipient_name

            # ✅ อัปเดต admin เฉพาะตอนที่ยังเป็น null
            if not p.admin_staff_name:
                p.admin_staff_name = admin["name"]

            db.commit()
            db.refresh(p)

            write_audit(
                db,
                entity="พัสดุ",
                entity_id=p.id,
                action="ยืนยันการรับพัสดุ",
                user=f"เจ้าหน้าที่: {admin['name']}",
                details=(
                    f"ผู้รับ: {p.recipient_name}"
                    f"\nหมายเลขพัสดุ: {p.tracking_number}"
                    f"\nเลขคิว: {p.queue_number}"
                    + (f"\nชื่อหน้ากล่อง: {p.unofficial_recipient}"
                    if p.unofficial_recipient else "")
                ),
            )

            db.commit()

            return {
                "ok": True,
                "message": "พัสดุรับไปแล้ว",
                "admin_staff_name": p.admin_staff_name,
                "picked_up_at": p.picked_up_at.isoformat()
            }

        # -----------------------------
        # กรณียังไม่รับ
        # -----------------------------
        p.status = "ได้รับแล้ว"
        p.recipient_name = payload.recipient_name

        # ✅ ใส่ admin ได้เลย (ยังไม่เคยรับ)
        p.admin_staff_name = admin["name"]
        p.picked_up_at = thai_now()

        db.commit()
        db.refresh(p)
        write_audit(
            db,
            entity="พัสดุ",
            entity_id=p.id,
            action="ยืนยันการรับพัสดุ",
            user=f"เจ้าหน้าที่: {admin['name']}",
            details=(
                    f"ผู้รับ: {p.recipient_name}"
                    f"\nหมายเลขพัสดุ: {p.tracking_number}"
                    f"\nเลขคิว: {p.queue_number}"
                    + (f"\nชื่อหน้ากล่อง: {p.unofficial_recipient}"
                    if p.unofficial_recipient else "")
                ),
        )
        db.commit()
        
        return {
            "ok": True,
            "tracking": p.tracking_number,
            "queue_number": p.queue_number,
            "admin_staff_name": p.admin_staff_name,
            "picked_up_at": p.picked_up_at.isoformat(),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }

    finally:
        db.close()

@app.post("/api/parcels/{tracking}/confirm_pickup/recipient")
def confirm_pickup_recipient(
    tracking: str,
    payload: ConfirmPickupIn,
    request: Request
):
    db = SessionLocal()
    recipient = request.session.get("recipient")
    if not recipient:
        raise HTTPException(status_code=401, detail="not logged in")

    try:
        tracking_clean = normalize_tracking_value(tracking)

        p = db.query(Parcel).filter(
            normalize_tracking_column(Parcel.tracking_number)
            == tracking_clean
        ).first()

        if not p:
            raise HTTPException(status_code=404, detail="parcel not found")

        # ---------- รับครั้งแรก ----------
        if payload.recipient_name:
            p.recipient_name = payload.recipient_name

        p.status = "ได้รับแล้ว"
        p.picked_up_at = thai_now()

        write_audit(
            db,
            entity="พัสดุ",
            entity_id=p.id,
            action="ได้รับพัสดุ",
            user=f"ผู้รับ: {recipient['name']}",
            details=(
                    f"หมายเลขพัสดุ: {p.tracking_number}"
                    f"\nเลขคิว: {p.queue_number}"
                    + (f"\nชื่อหน้ากล่อง: {p.unofficial_recipient}"
                    if p.unofficial_recipient else "")
                ),
        )

        db.commit()

        return {
            "ok": True,
            "tracking": p.tracking_number,
            "queue_number": p.queue_number,
            "recipient": p.recipient_name,
            "picked_up_at": p.picked_up_at.isoformat(),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }

    finally:
        db.close()

# ---------------------------
# Reports: dates (for dropdown), summary, timeseries, export
# ---------------------------
@app.get("/api/reports/dates")
def get_available_periods(period: str = Query("daily", regex="^(daily|monthly|yearly)$"),admin = Depends(require_admin)):
    db = SessionLocal()
    try:
        rows = db.query(Parcel).order_by(Parcel.created_at).all()
        counts = {}
        for p in rows:
            dt = p.created_at
            if not dt:
                continue
            if period == "daily":
                key = dt.strftime("%Y%m%d")
            elif period == "monthly":
                key = dt.strftime("%Y%m")
            else:
                key = dt.strftime("%Y")
            counts[key] = counts.get(key, 0) + 1
        out = [{"period": k, "count": counts[k]} for k in sorted(counts.keys(), reverse=True)]
        return out
    finally:
        db.close()

@app.get("/api/reports/summary")
def report_summary(
    period: str = Query("daily", regex="^(daily|monthly|yearly)$"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    admin = Depends(require_admin)
):
    db = SessionLocal()
    try:
        rows = db.query(Parcel).order_by(Parcel.created_at.desc()).all()

        checkin = 0
        checkout = 0
        items = []

        for p in rows:
            dt = p.created_at
            if not dt:
                continue

            if period == "daily":
                key = dt.strftime("%Y%m%d")
            elif period == "monthly":
                key = dt.strftime("%Y%m")
            else:
                key = dt.strftime("%Y")

            if start and key < start:
                continue
            if end and key > end:
                continue

            checkin += 1
            if p.status == "ได้รับแล้ว":
                checkout += 1

            items.append({
                "id": p.id,
                "tracking": p.tracking_number,
                "queue": p.queue_number,
                "status": p.status,
                "recipient": p.recipient_name,
                "created_at": dt.isoformat() if dt else None,
                "picked_up_at": p.picked_up_at.isoformat() if p.picked_up_at else None
            })

        remaining = checkin - checkout

        return {
            "period": period,
            "start": start,
            "end": end,
            "checkin": checkin,
            "checkout": checkout,
            "remaining": remaining,
            "items": items
        }

    finally:
        db.close()

@app.get("/api/reports/timeseries")
def reports_timeseries(period: str = Query("daily", regex="^(daily|monthly|yearly)$"),
                       start: Optional[str] = None, end: Optional[str] = None, limit: int = 365,admin = Depends(require_admin)):
    db = SessionLocal()
    try:
        rows = db.query(Parcel).order_by(Parcel.created_at).all()
        agg: dict[str, dict[str, int]] = {}
        for p in rows:
            dt = p.created_at
            if not dt:
                continue
            if period == "daily":
                key = dt.strftime("%Y%m%d")
            elif period == "monthly":
                key = dt.strftime("%Y%m")
            else:
                key = dt.strftime("%Y")
            if start and key < start:
                continue
            if end and key > end:
                continue
            if key not in agg:
                agg[key] = {"checkin": 0, "checkout": 0}
            agg[key]["checkin"] += 1
            if p.status == "ได้รับแล้ว":
                agg[key]["checkout"] += 1
        keys_sorted = sorted(agg.keys())
        if len(keys_sorted) > limit:
            keys_sorted = keys_sorted[-limit:]
        labels = []
        checkin = []
        checkout = []
        for k in keys_sorted:
            labels.append(k)
            checkin.append(agg[k]["checkin"])
            checkout.append(agg[k]["checkout"])
        return {"labels": labels, "checkin": checkin, "checkout": checkout}
    finally:
        db.close()

@app.get("/api/reports/export")
def export_report(
    period: str = "daily",
    start: Optional[str] = None,
    end: Optional[str] = None,
    fmt: str = "csv",
    admin = Depends(require_admin)
):
    """
    Export report filtered by period/date into CSV or XLSX.
    - period: daily|monthly|yearly
    - date: for daily -> 'YYYYMMDD', monthly -> 'YYYYMM', yearly -> 'YYYY'
    - fmt: 'csv' or 'xlsx'
    The exported file will contain 3 summary rows at the top:
      Check-in: N
      Check-out: M
      Remaining: K
    then an empty line, then the table with columns:
      id, tracking_number, queue_number, status, recipient_name, admin_staff_name, created_at
    """
    db = SessionLocal()
    try:
        # load and filter same as report_summary logic
        rows = db.query(Parcel).order_by(Parcel.created_at.desc()).all()

        items = []
        checkin = 0
        checkout = 0

        for p in rows:
            dt = p.created_at
            # if date filter provided, compute key and compare
            if period == "daily":
                key = dt.strftime("%Y%m%d")
            elif period == "monthly":
                key = dt.strftime("%Y%m")
            else:
                key = dt.strftime("%Y")

            if start and key < start:
                continue
            if end and key > end:
                continue

            checkin += 1
            if p.status == "ได้รับแล้ว":
                checkout += 1

            items.append({
                "id": p.id,
                "tracking_number": p.tracking_number,
                "queue_number": p.queue_number,
                "status": p.status,
                "recipient_name": p.recipient_name,
                "admin_staff_name": p.admin_staff_name,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "picked_up_at": p.picked_up_at.isoformat() if p.picked_up_at else None
            })

        remaining = checkin - checkout
        # ---------- format period to thai date ----------
        def fmt_key(k: str | None):
            if not k:
                return ""
            try:
                if period == "daily" and len(k) == 8:
                    d = datetime.strptime(k, "%Y%m%d")
                    return d.strftime("%d/%m/%Y")
                if period == "monthly" and len(k) == 6:
                    d = datetime.strptime(k, "%Y%m")
                    return d.strftime("%m/%Y")
                if period == "yearly" and len(k) == 4:
                    return k
            except Exception:
                pass
            return k

        start_fmt = fmt_key(start)
        end_fmt = fmt_key(end)

    finally:
        db.close()

    # Prepare filename
    safe_start = (start_fmt or "ทั้งหมด").replace("/", "-")
    safe_end = (end_fmt or "ทั้งหมด").replace("/", "-")
    fname_base = f"รายงานพัสดุ_ช่วงวันที่_{safe_start}_ถึง_{safe_end}"
    # CSV branch (or fallback if pandas not available)
    if fmt == "csv" or not PANDAS_AVAILABLE:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        # ===== period =====
        writer.writerow(["ช่วงวันที่", f"{start_fmt} ถึง {end_fmt}"])
        writer.writerow([])
        # ===== summary =====
        writer.writerow(["พัสดุเข้า", checkin])
        writer.writerow(["พัสดุออก", checkout])
        writer.writerow(["พัสดุคงเหลือ", remaining])
        writer.writerow([])

        # ===== thai header =====
        headers = [
            "เลขคิว",
            "เลขพัสดุ",
            "สถานะ",
            "ชื่อผู้รับ",
            "ชื่อเจ้าหน้าที่",
            "วันที่พัสดุเข้า"
        ]
        writer.writerow(headers)

        # ===== rows =====
        for r in items:
            writer.writerow([
                r.get("queue_number"),
                r.get("tracking_number"),
                r.get("status"),
                r.get("recipient_name"),
                r.get("admin_staff_name"),
                r.get("created_at")
            ])
        filename = f"{fname_base}.csv"
        filename_star = quote(filename)
        content = buffer.getvalue()
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8-sig",   # ✅ Excel เปิดไทยไม่เพี้ยน
            headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{filename_star}"}
        )

    # XLSX branch using pandas -> openpyxl engine
    # We'll write the summary in the top rows and the dataframe starting at row 5 (index 4)
    df = pd.DataFrame(items)
    # Ensure all columns exist in DataFrame (in correct order)
    cols = ["id", "tracking_number", "queue_number", "status", "recipient_name",  "created_at"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # write dataframe starting at row index 4 (Excel row 5) so we have room for 3 summary rows + blank line
        df.to_excel(writer, index=False, sheet_name="parcels", startrow=4)

        # write summary on top-left of the same sheet
        ws = writer.sheets["parcels"]
        # Excel rows are 1-indexed
        ws.cell(row=1, column=1, value="พัสดุเข้า")
        ws.cell(row=1, column=2, value=checkin)
        ws.cell(row=2, column=1, value="พัสดุออก")
        ws.cell(row=2, column=2, value=checkout)
        ws.cell(row=3, column=1, value="พัสดุคงเหลือ")
        ws.cell(row=3, column=2, value=remaining)

        # optionally freeze panes so header is visible
        ws.freeze_panes = "A6"

    buffer.seek(0)

    filename = f"{fname_base}.xlsx"
    filename_star = quote(filename)
    return Response(
        content=buffer.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{filename_star}"}
    )


    if fmt == "csv" or not PANDAS_AVAILABLE:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=rows[0].keys() if rows else ["id", "tracking_number"])
        writer.writeheader()
        if rows:
            writer.writerows(rows)
        return Response(content=buffer.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="parcel_report_{period}_{date or "all"}.csv"'})
    else:
        df = pd.DataFrame(rows)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="parcels")
        buffer.seek(0)
        return Response(content=buffer.read(),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="parcel_report_{period}_{date or "all"}.xlsx"'})
    
# ---------------------------
# Admin: Bulk delete parcels
# ---------------------------
@app.post("/api/parcels/bulk_delete")
def bulk_delete_parcels(
    payload: BulkDeleteIn,
    request: Request,
    admin = Depends(require_admin)
):
    if not payload.ids and not payload.trackings:
        raise HTTPException(status_code=400, detail="ids or trackings required")

    admin_name = admin["name"] 

    db = SessionLocal()
    try:
        q = db.query(Parcel)

        if payload.ids:
            q = q.filter(Parcel.id.in_(payload.ids))
        if payload.trackings:
            q = q.filter(Parcel.tracking_number.in_(payload.trackings))

        to_delete = q.all()
        if not to_delete:
            return {"ok": True, "deleted": 0}

        count = len(to_delete)

        for p in to_delete:
            db.delete(p)

        
            write_audit(
                db,
                entity="พัสดุ",
                entity_id=p.id,
                action="ลบรายการพัสดุ",
                user=f"เจ้าหน้าที่: {admin_name}",
                details=(
                    f"หมายเลขพัสดุ: {p.tracking_number}"
                    f"\nเลขคิว: {p.queue_number}"
                    + (f"\nชื่อหน้ากล่อง: {p.unofficial_recipient}"
                    if p.unofficial_recipient else "")
                ),
            )

        db.commit()
        return {"ok": True, "deleted": count}

    finally:
        db.close()

# ---------------------------
# Delete provisional parcel (from client preview)
# ---------------------------
@app.delete("/api/parcels/{tracking}")
def delete_parcel(tracking: str, db: Session = Depends(get_db)):

    tracking_clean = normalize_tracking_value(tracking)

    parcel = db.query(Parcel).filter(
        normalize_tracking_column(Parcel.tracking_number)
        == tracking_clean
    ).first()

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    if parcel.status != "กำลังรอ":
        raise HTTPException(
            status_code=400,
            detail=""
        )
    section_id = parcel.section_id

    # 🔥 หา reservation ของ section นี้
    reservation = db.query(QueueReservation).filter(
        QueueReservation.section_id == section_id,
        QueueReservation.date == thai_now().strftime("%Y%m%d")
    ).order_by(QueueReservation.current_seq.desc()).first()


    # ✅ ลบ parcel
    db.delete(parcel)

    # 🔥 ลด current_seq ลง 1 (แต่ห้ามต่ำกว่า start_seq - 1)
    if reservation:
        new_seq = reservation.current_seq - 1
        min_seq = reservation.start_seq - 1
        reservation.current_seq = max(new_seq, min_seq)

        # 🔥 FIX: อัปเดต status ใหม่
        if reservation.current_seq < reservation.end_seq:
            reservation.status = "active"
        else:
            reservation.status = "full"
    db.commit()

    return {"message": "Deleted and sequence updated"}


@app.get("/api/carriers")
def list_carriers():
    db = SessionLocal()
    try:
        rows = db.query(CarrierList).all()
        return [
            {
                "carrier_id": c.carrier_id,
                "carrier_name": c.carrier_name,
                "logo": c.logo
            }
            for c in rows
        ]
    finally:
        db.close()

from sqlalchemy import or_

@app.get("/api/audit_logs")
def list_audit_logs(
    limit: int = 1000,
    before: str | None = None,
    q: str | None = None,
    action: str | None = None,
    date: str | None = None, 
    admin = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
        # ---------- date filter ----------
    

    if date:
        day = datetime.strptime(date, "%Y-%m-%d")

        # ไทย = UTC+7
        start_local = day.replace(
            hour=0, minute=0, second=0, microsecond=0,
            tzinfo=timezone(timedelta(hours=7))
        )

        start_utc = start_local.astimezone(timezone.utc)
        end_utc = start_utc + timedelta(days=1)

        query = query.filter(
            AuditLog.timestamp >= start_utc,
            AuditLog.timestamp < end_utc
        )

    # filter action
    if action:
        query = query.filter(AuditLog.action == action)

    # search
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                AuditLog.user.ilike(like),
                AuditLog.details.ilike(like),
                AuditLog.entity.ilike(like),
            )
        )

    # 👇 load older than timestamp
    if before:
        try:
            before_dt = datetime.fromisoformat(before)
            query = query.filter(AuditLog.timestamp < before_dt)
        except Exception:
            pass

    logs = (
        query
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": l.id,
            "entity": l.entity,
            "entity_id": l.entity_id,
            "action": l.action,
            "user": l.user,
            "details": l.details,
            "timestamp": l.timestamp.isoformat()
        }
        for l in logs
    ]
from .models import QueueReservation

@app.post("/api/queue/init")
def init_sections():
    db = SessionLocal()
    try:
        exists = db.query(QueueSection).first()
        if exists:
            return {"message": "already initialized"}

        start = 1
        for i in range(20):
            end = start + 49

            db.add(QueueSection(
                start_seq=start,
                end_seq=end,
            ))

            start = end + 1

        db.commit()
        return {"message": "20 sections created"}

    finally:
        db.close()


# 🔥 ต้องอยู่นอก finally
@app.get("/api/queue/sections")
def get_sections(db: Session = Depends(get_db)):

    sections = (
        db.query(QueueSection)
        .order_by(QueueSection.start_seq)
        .all()
    )

    result = []

    for s in sections:

        total = s.end_seq - s.start_seq + 1

        used = db.query(func.count(Parcel.id)).filter(
            Parcel.section_id == s.id
        ).scalar()

        remaining = total - used

        result.append({
            "id": s.id,
            "start_seq": s.start_seq,
            "end_seq": s.end_seq,
            "total": total,
            "used": used,
            "remaining": remaining
        })

    return result

# 🔥 ต้องอยู่นอก finally
from sqlalchemy import func

@app.get("/api/queue/sections_available")
def get_available_sections(
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    today = thai_now().strftime("%Y%m%d")

    sections = db.query(QueueSection).order_by(
        QueueSection.start_seq
    ).all()

    result = []

    for s in sections:

        reservation = db.query(QueueReservation).filter(
            QueueReservation.section_id == s.id,
            QueueReservation.date == today
        ).order_by(QueueReservation.id.desc()).first()

        # default
        current_seq = s.start_seq - 1
        status = "available"

        if reservation:

            current_seq = reservation.current_seq or (s.start_seq - 1)

            # 🔥 1) ถ้าเต็ม
            if reservation.status == "full":
                status = "full"

            # 🔥 2) ถ้ายัง active
            elif reservation.status == "active":

                if reservation.user_id == user_id:
                    status = "mine"
                else:
                    status = "blocked"

            # 🔥 3) ถ้า unactive
            elif reservation.status == "unactive":
                status = "available"

        result.append({
            "id": s.id,
            "start_seq": s.start_seq,
            "end_seq": s.end_seq,
            "status": status,
            "current_seq": current_seq
        })

    return result



from typing import List

class ReserveIn(BaseModel):
    section_ids: List[int]

from datetime import datetime
@app.post("/api/queue/reserve")
def reserve_section(
    payload: ReserveIn,
    request: Request,
    db: Session = Depends(get_db)
):
    carrier_id = request.session.get("carrier_id")
    user_id = request.session.get("user_id")

    if not carrier_id:
        raise HTTPException(401, "not logged in")

    today = thai_now().strftime("%Y%m%d")

    sections = db.query(QueueSection).filter(
        QueueSection.id.in_(payload.section_ids)
    ).all()

    if not sections:
        raise HTTPException(400, "invalid section")

    for s in sections:

        # 🔥 หา current_seq สูงสุดของวันนี้ใน section นี้
        last_used = db.query(func.max(QueueReservation.current_seq)).filter(
            QueueReservation.section_id == s.id,
            QueueReservation.date == today
        ).scalar()

        if last_used is None:
            start_current = s.start_seq - 1
        else:
            start_current = last_used

        # 🔥 เช็คว่ามี active อยู่ไหม
        active = db.query(QueueReservation).filter(
            QueueReservation.section_id == s.id,
            QueueReservation.date == today,
            QueueReservation.status == "active"
        ).first()

        if active:
            raise HTTPException(
                400,
                f"Section {s.start_seq}-{s.end_seq} กำลังใช้งานอยู่"
            )

        # 🔥 สร้าง reservation ใหม่ โดยใช้ current ต่อจากของเดิม
        r = QueueReservation(
            section_id=s.id,
            carrier_id=carrier_id,
            user_id=user_id,
            date=today,
            start_seq=s.start_seq,
            end_seq=s.end_seq,
            current_seq=start_current,   # ✅ สำคัญ
            status="active"
        )

        db.add(r)

    db.commit()

    return {"message": "reserved"}



class CancelIn(BaseModel):
    section_ids: list[int]
@app.post("/api/queue/cancel")
def cancel_reservation(
    payload: CancelIn,
    request: Request,
    db: Session = Depends(get_db)
):
    carrier_id = request.session.get("carrier_id")
    user_id = request.session.get("user_id")

    if not carrier_id:
        raise HTTPException(401, "not logged in")

    today = thai_now().strftime("%Y%m%d")
    deleted = 0

    for sid in payload.section_ids:

        reservation = db.query(QueueReservation).filter(
            QueueReservation.section_id == sid,
            QueueReservation.date == today,
            QueueReservation.user_id == user_id
        ).order_by(QueueReservation.id.desc()).first()

        if not reservation:
            continue

        # 1️⃣ ลบพัสดุที่ยังรอ
        db.query(Parcel).filter(
            Parcel.section_id == sid,
            Parcel.carrier_id == carrier_id,
            Parcel.status == "กำลังรอ"
        ).delete(synchronize_session=False)

        # 2️⃣ ลบ reservation record เลย
        db.delete(reservation)

        deleted += 1

    db.commit()

    return {"deleted": deleted}
# EOF