from datetime import date, timedelta

from sqlalchemy import text

from src.core.database import Database


class SlotUnavailableError(Exception):
    pass


async def get_active_services(db: Database) -> list[dict[str, object]]:
    async with db.session() as conn:
        result = await conn.execute(
            text("SELECT id, name, duration_min, price FROM services WHERE is_active = 1 ORDER BY name")
        )
        return [dict(row._mapping) for row in result.all()]


async def get_service(db: Database, service_id: int) -> dict[str, object] | None:
    async with db.session() as conn:
        result = await conn.execute(text("SELECT * FROM services WHERE id = :id"), {"id": service_id})
        row = result.first()
        return dict(row._mapping) if row else None


async def get_schedule(db: Database, day_of_week: int) -> list[dict[str, object]]:
    async with db.session() as conn:
        result = await conn.execute(
            text("SELECT * FROM weekly_schedule WHERE day_of_week = :dow ORDER BY start_time"),
            {"dow": day_of_week},
        )
        return [dict(row._mapping) for row in result.all()]


async def get_available_dates(db: Database, service_id: int, days_ahead: int = 14) -> list[str]:
    service = await get_service(db, service_id)
    if not service:
        return []

    today_date = date.today()
    dates: list[str] = []

    for i in range(1, days_ahead + 1):
        d = today_date + timedelta(days=i)
        dow = d.weekday()
        schedule = await get_schedule(db, dow)
        if not schedule:
            continue

        date_str = d.isoformat()
        async with db.session() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM slots WHERE service_id = :sid AND date = :date AND is_booked = 0"),
                {"sid": service_id, "date": date_str},
            )
            free = result.scalar_one()
            if free and free > 0:
                dates.append(date_str)

    return dates


async def get_free_slots(db: Database, service_id: int, date_str: str) -> list[dict[str, object]]:
    async with db.session() as conn:
        result = await conn.execute(
            text(
                "SELECT id, start_time, end_time FROM slots "
                "WHERE service_id = :sid AND date = :date AND is_booked = 0 ORDER BY start_time"
            ),
            {"sid": service_id, "date": date_str},
        )
        return [dict(row._mapping) for row in result.all()]


async def book_slot(db: Database, *, service_id: int, slot_id: int, user_id: int, name: str, phone: str) -> int:
    async with db.transaction() as conn:
        result = await conn.execute(
            text("UPDATE slots SET is_booked = 1 WHERE id = :id AND is_booked = 0"),
            {"id": slot_id},
        )
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise SlotUnavailableError()

        slot = await conn.execute(text("SELECT date, start_time FROM slots WHERE id = :id"), {"id": slot_id})
        slot_row = slot.first()
        if slot_row is None:
            raise SlotUnavailableError()

        result = await conn.execute(
            text(
                "INSERT INTO bookings "
                "(service_id, slot_id, client_user_id, client_name, "
                "client_phone, booking_date, start_time, status) "
                "VALUES (:sid, :slot, :uid, :name, :phone, :date, :time, 'confirmed') "
                "RETURNING id"
            ),
            {
                "sid": service_id,
                "slot": slot_id,
                "uid": user_id,
                "name": name,
                "phone": phone,
                "date": slot_row[0],
                "time": slot_row[1],
            },
        )
        row = result.first()
        return int(row[0]) if row else 0


async def get_user_bookings(db: Database, user_id: int) -> list[dict[str, object]]:
    async with db.session() as conn:
        result = await conn.execute(
            text(
                "SELECT b.id, s.name as service_name, b.booking_date, b.start_time, b.status "
                "FROM bookings b JOIN services s ON b.service_id = s.id "
                "WHERE b.client_user_id = :uid AND b.status IN ('confirmed', 'pending') "
                "ORDER BY b.booking_date, b.start_time"
            ),
            {"uid": user_id},
        )
        return [dict(row._mapping) for row in result.all()]


async def cancel_booking(db: Database, booking_id: int, user_id: int) -> bool:
    async with db.transaction() as conn:
        result = await conn.execute(
            text(
                "UPDATE bookings SET status = 'cancelled' "
                "WHERE id = :id AND client_user_id = :uid AND status IN ('confirmed', 'pending')"
            ),
            {"id": booking_id, "uid": user_id},
        )
        if result.rowcount and result.rowcount > 0:  # type: ignore[attr-defined]
            booking = await conn.execute(text("SELECT slot_id FROM bookings WHERE id = :id"), {"id": booking_id})
            slot_row = booking.first()
            if slot_row and slot_row[0]:
                await conn.execute(text("UPDATE slots SET is_booked = 0 WHERE id = :id"), {"id": slot_row[0]})
            return True
        return False


async def delete_user_data(db: Database, user_id: int) -> int:
    """Delete all personal data for a user. Returns number of bookings removed."""
    async with db.transaction() as conn:
        await conn.execute(text("DELETE FROM reminders WHERE user_id = :uid"), {"uid": user_id})
        await conn.execute(text("DELETE FROM feedback WHERE user_id = :uid"), {"uid": user_id})
        result = await conn.execute(text("DELETE FROM bookings WHERE client_user_id = :uid"), {"uid": user_id})
        deleted = int(result.rowcount or 0)  # type: ignore[attr-defined]
    return deleted


async def log_audit(db: Database, user_id: int, action: str) -> None:
    async with db.transaction() as conn:
        await conn.execute(
            text("INSERT INTO audit_log (client_user_id, action) VALUES (:uid, :action)"),
            {"uid": user_id, "action": action},
        )
