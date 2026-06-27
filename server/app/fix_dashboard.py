# -*- coding: utf-8 -*-
"""
Rewrites the dashboard_today endpoint in api.py:
 - Removes carrier section
 - Fixes section utilization to use current_seq from QueueReservation (same as Client sees)
"""

import os
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api.py')

content = open(path, encoding='utf-8').read()

new_dashboard = r'''# ---------------------------
# Dashboard today
# ---------------------------
@app.get("/api/dashboard/today")
def dashboard_today(admin=Depends(require_admin)):
    """
    รวมข้อมูลสำหรับ Dashboard หน้าภาพรวม ใน 1 call:
    - KPI วันนี้ (เข้า / รับออก / รอรับ)
    - แยกตามสถานะ (กำลังรอ / ยังไม่ได้รับ / ได้รับแล้ว)
    - Section utilization (อ้างอิง current_seq ของ reservation วันนี้ เหมือน Client เห็น)
    - จำนวนพัสดุตกค้าง >30 วัน (preview)
    """
    db = SessionLocal()
    try:
        tz_thai = timezone(timedelta(hours=7))
        now = thai_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=tz_thai)

        # วันนี้ (00:00-23:59 เวลาไทย)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end   = today_start + timedelta(days=1)
        today_str   = now.strftime("%Y%m%d")

        today_parcels = db.query(Parcel).filter(
            Parcel.created_at >= today_start,
            Parcel.created_at <  today_end
        ).all()

        # KPI
        total_in    = len(today_parcels)
        total_out   = sum(1 for p in today_parcels if p.status == "ได้รับแล้ว")
        total_wait  = sum(1 for p in today_parcels if p.status != "ได้รับแล้ว")

        # แยกสถานะ
        status_pending   = sum(1 for p in today_parcels if p.status == "กำลังรอ")
        status_waiting   = sum(1 for p in today_parcels if p.status == "ยังไม่ได้รับ")
        status_done      = total_out

        # Section utilization - อ้างอิง current_seq ของ reservation วันนี้
        # เหมือนกับที่ Client เห็นใน /api/queue/sections_available
        sections = db.query(QueueSection).order_by(QueueSection.start_seq).all()
        section_data = []
        for s in sections:
            total_slots = s.end_seq - s.start_seq + 1

            # หา reservation ล่าสุดของวันนี้สำหรับ section นี้
            reservation = (
                db.query(QueueReservation)
                .filter(
                    QueueReservation.section_id == s.id,
                    QueueReservation.date == today_str
                )
                .order_by(QueueReservation.id.desc())
                .first()
            )

            if reservation:
                # จำนวนที่ใช้ไปแล้ว = current_seq - (start_seq - 1)
                used = max(0, reservation.current_seq - (s.start_seq - 1))
                res_status = reservation.status  # active / full / unactive
            else:
                used = 0
                res_status = "available"

            pct = round(used / total_slots * 100) if total_slots else 0
            section_data.append({
                "id":         s.id,
                "start_seq":  s.start_seq,
                "end_seq":    s.end_seq,
                "total":      total_slots,
                "used":       used,
                "pct":        pct,
                "res_status": res_status
            })

        # พัสดุตกค้าง >30 วัน (preview count)
        from sqlalchemy import func as sqlfunc
        cutoff_30 = now - timedelta(days=30)
        stranded_count = db.query(sqlfunc.count(Parcel.id)).filter(
            Parcel.status.in_(["ยังไม่ได้รับ", "กำลังรอ"]),
            Parcel.created_at <= cutoff_30
        ).scalar() or 0

        return {
            "kpi": {
                "total_in":   total_in,
                "total_out":  total_out,
                "total_wait": total_wait
            },
            "status_breakdown": {
                "pending":  status_pending,
                "waiting":  status_waiting,
                "done":     status_done
            },
            "sections": section_data,
            "stranded_30d": stranded_count,
            "generated_at": now.isoformat()
        }
    finally:
        db.close()

# EOF'''

marker = '# ---------------------------\n# Dashboard today\n# ---------------------------'
idx = content.index(marker)
new_content = content[:idx] + new_dashboard
open(path, 'w', encoding='utf-8').write(new_content)
lines = new_content.count('\n')
print(f'Done. Total lines: {lines}')
