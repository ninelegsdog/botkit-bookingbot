import asyncio

from src.app import collect_routers
from src.core.auth import AdminGate
from src.core.bot_factory import build_dispatcher, create_bot
from src.core.config import Settings
from src.core.database import Database
from src.core.errors import RetryMiddleware, register_error_handler
from src.core.metrics import UpdatesMiddleware, start_metrics_server
from src.core.migrations import MigrationRegistry
from src.core.navigation import NavRegistry
from src.core.sentry import init_sentry
from src.core.storage import create_storage
from src.core.throttling import ThrottlingMiddleware


async def main() -> None:
    settings = Settings()
    init_sentry(settings.sentry_dsn)
    registry = MigrationRegistry()

    from src.booking.models import register_migrations

    register_migrations(registry)

    nav = NavRegistry()
    db = Database(settings.database_url)
    await db.init_database(registry)

    gate = AdminGate(settings.admin_password)
    routers = collect_routers(gate=gate, nav=nav, db=db)

    dp = build_dispatcher(
        routers=routers,
        storage=create_storage(settings.redis_url),
        throttling=ThrottlingMiddleware(
            rate_limit=settings.throttle_rate_limit,
            max_idle=settings.throttle_max_idle,
        ),
    )
    dp.update.outer_middleware(UpdatesMiddleware())
    dp.message.middleware(RetryMiddleware())
    register_error_handler(dp)
    bot = create_bot(settings.bot_token)
    await bot.delete_webhook(drop_pending_updates=True)
    runner = await start_metrics_server(settings.metrics_port)
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
