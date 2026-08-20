import asyncio
import logging

from aiogram import Bot

from src.core.database import Database
from src.reminder import service

logger = logging.getLogger(__name__)


async def scheduler_loop(db: Database, bot: Bot, interval: int = 60) -> None:
    while True:
        try:
            due = await service.get_due_reminders(db)
            for r in due:
                try:
                    await bot.send_message(r["user_id"], f"⏰ {r['text']}")
                    await service.mark_sent(db, r["id"])
                except Exception as e:
                    logger.warning("Failed to send reminder %s: %s", r["id"], e)
        except Exception as e:
            logger.error("Scheduler error: %s", e)
        await asyncio.sleep(interval)
