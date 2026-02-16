from datetime import date
from .models import DailyCounter, RecycledQueue,QueueReservation
from .db import SessionLocal


def format_queue(seq: int) -> str:
    return f"{seq}"

def reserve_queue_range(carrier_id: int, amount: int):
    today = date.today()
    datestr = today.strftime("%Y%m%d")

    db = SessionLocal()
    try:
        with db.begin():

            counter = (
                db.query(DailyCounter)
                .filter(
                    DailyCounter.carrier_id == carrier_id,
                    DailyCounter.date == datestr
                )
                .with_for_update()
                .one_or_none()
            )

            if counter is None:
                counter = DailyCounter(
                    carrier_id=carrier_id,
                    date=datestr,
                    last_seq=0
                )
                db.add(counter)
                db.flush()

            start_seq = counter.last_seq + 1
            end_seq = counter.last_seq + amount

            counter.last_seq = end_seq

            reservation = QueueReservation(
                carrier_id=carrier_id,
                date=datestr,
                start_seq=start_seq,
                end_seq=end_seq
            )
            db.add(reservation)

        return start_seq, end_seq

    finally:
        db.close()