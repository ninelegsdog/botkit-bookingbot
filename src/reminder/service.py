from datetime import datetime

from sqlalchemy import text

from src.core.database import Database


async def create_reminder(
    db: Database, *, booking_id: int, user_id: int, fire_at: datetime, reminder_text: str
) -> int:
    async with db.transaction() as conn:
        result = await conn.execute(
            text(
                "INSERT INTO reminders (booking_id, user_id, fire_at, text, is_active) "
                "VALUES (:bid, :uid, :fire, :text, 1) RETURNING id"
            ),
            {"bid": booking_id, "uid": user_id, "fire": fire_at.isoformat(), "text": reminder_text},
        )
        row = result.first()
        return int(row[0]) if row else 0


async def get_due_reminders(db: Database) -> list[dict[str, int | str]]:
    async with db.session() as conn:
        result = await conn.execute(
            text(
                "SELECT id, user_id, text FROM reminders "
                "WHERE is_active = 1 AND fire_at <= :now"
            ),
            {"now": datetime.now().isoformat()},
        )
        return [dict(row._mapping) for row in result.all()]


async def mark_sent(db: Database, reminder_id: int) -> None:
    async with db.transaction() as conn:
        await conn.execute(
            text("UPDATE reminders SET is_active = 0 WHERE id = :id"),
            {"id": reminder_id},
        )
