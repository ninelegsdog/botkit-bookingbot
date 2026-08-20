from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


def create_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def build_dispatcher(
    *, routers: list[Any] | None = None, storage: Any = None, throttling: Any = None
) -> Dispatcher:
    kwargs: dict[str, Any] = {}
    if storage:
        kwargs["storage"] = storage
    dp = Dispatcher(**kwargs)
    if throttling:
        dp.message.middleware(throttling)
    if routers:
        for router in routers:
            dp.include_router(router)
    return dp
