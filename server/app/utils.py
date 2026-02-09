from datetime import date
from .models import DailyCounter, RecycledQueue
from .db import SessionLocal


def format_queue(seq: int) -> str:
    return f"{seq}"


def next_queue_number_atomic(today: date | None = None):
    if today is None:
        today = date.today()

    datestr = today.strftime("%Y%m%d")

    db = SessionLocal()
    try:
        with db.begin():

            # ✅ 1) ใช้คิวที่ถูกคืนก่อน (ไม่สน carrier)
            recycled = (
                db.query(RecycledQueue)
                .filter(RecycledQueue.date == datestr)
                .order_by(RecycledQueue.queue_number.asc())
                .with_for_update()
                .first()
            )

            if recycled:
                queue = recycled.queue_number
                db.delete(recycled)
                return queue

            # ✅ 2) counter รายวัน (เดียวทั้งระบบ)
            counter = (
                db.query(DailyCounter)
                .filter(DailyCounter.date == datestr)
                .with_for_update()
                .one_or_none()
            )

            if counter is None:
                counter = DailyCounter(
                    date=datestr,
                    last_seq=1
                )
                db.add(counter)
                seq = 1
            else:
                counter.last_seq += 1
                seq = counter.last_seq

        return format_queue(seq)

    finally:
        db.close()
