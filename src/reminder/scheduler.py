import asyncio
import logging

from aiogram import Bot

from src.core.database import Database
from src.reminder import service

logger = logging.getLogger(__name__)


async def send_due_reminders(db: Database, bot: Bot) -> int:
    """One pass over the due reminders. Returns how many were sent."""
    sent = 0
    due = await service.get_due_reminders(db)
    for r in due:
        try:
            await bot.send_message(int(r["user_id"]), f"⏰ {r['text']}")
            await service.mark_sent(db, int(r["id"]))
            sent += 1
        except Exception as e:
            logger.warning("Failed to send reminder %s: %s", r["id"], e)
    return sent


async def scheduler_loop(db: Database, bot: Bot, interval: int = 60) -> None:
    while True:
        try:
            await send_due_reminders(db, bot)
        except Exception as e:
            logger.error("Scheduler error: %s", e)
        await asyncio.sleep(interval)
