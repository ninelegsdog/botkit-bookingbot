import asyncio
import logging
import signal
from pathlib import Path
from typing import Any

from aiogram.types import BufferedInputFile
from aiohttp import web

from src.app import collect_routers
from src.core.auth import AdminGate
from src.core.bot_factory import build_dispatcher, create_bot
from src.core.config import Settings
from src.core.database import Database
from src.core.errors import RetryMiddleware, register_error_handler
from src.core.logging import LoggingMiddleware, setup_logging
from src.core.metrics import UpdatesMiddleware, health, metrics, start_metrics_server, version
from src.core.migrations import MigrationRegistry
from src.core.navigation import NavRegistry
from src.core.sentry import init_sentry
from src.core.storage import create_storage
from src.core.throttling import ThrottlingMiddleware
from src.core.tracing import TracingMiddleware, setup_tracing
from src.core.webhook import build_webhook_app

logger = logging.getLogger(__name__)


def _build_webhook_app(dp: Any, bot: Any, settings: Settings) -> web.Application:
    app = build_webhook_app(dp, bot, settings.webhook_secret_token)
    app.router.add_get("/health", health)
    app.router.add_get("/version", version)
    app.router.add_get("/metrics", metrics)
    return app


def _load_cert(path: str) -> BufferedInputFile | None:
    cert_path = Path(path)
    if not cert_path.is_file():
        return None
    return BufferedInputFile(cert_path.read_bytes(), filename="webhook_public.pem")


async def _run_webhook(settings: Settings, dp: Any, bot: Any, shutdown_event: asyncio.Event) -> None:
    app = _build_webhook_app(dp, bot, settings)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.metrics_port)
    await site.start()
    logger.info("Webhook HTTP server listening on :%s", settings.metrics_port)

    await bot.delete_webhook(drop_pending_updates=True)
    cert = await asyncio.to_thread(_load_cert, settings.webhook_cert_path)
    if cert is None:
        logger.warning("WEBHOOK_CERT_PATH not found: %s", settings.webhook_cert_path)
    else:
        logger.info("Using webhook certificate")
    await bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.webhook_secret_token or None,
        certificate=cert,
    )
    logger.info("Telegram webhook registered: %s", settings.webhook_url)
    try:
        await shutdown_event.wait()
    finally:
        await bot.delete_webhook()
        await runner.cleanup()


async def _run_polling(settings: Settings, dp: Any, bot: Any, shutdown_event: asyncio.Event) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    runner = await start_metrics_server(settings.metrics_port)
    try:
        await asyncio.wait([
            asyncio.create_task(dp.start_polling(bot)),
            asyncio.create_task(shutdown_event.wait()),
        ])
    finally:
        await dp.stop_polling()
        await bot.session.close()
        await runner.cleanup()


async def main() -> None:
    settings = Settings()
    setup_logging(level="INFO", json=True, bot_name="bookingbot")
    setup_tracing(service_name="bookingbot")
    init_sentry(settings.sentry_dsn)
    registry = MigrationRegistry()

    from src.booking.models import register_migrations

    register_migrations(registry)

    nav = NavRegistry()
    db = Database(settings.database_url)
    await db.init_database(registry)

    gate = AdminGate(settings.admin_password, settings.admin_ids)
    routers = collect_routers(gate=gate, nav=nav, db=db)

    dp = build_dispatcher(
        routers=routers,
        storage=create_storage(settings.redis_url),
        throttling=ThrottlingMiddleware(
            redis_url=settings.redis_url,
            rate_limit=settings.throttle_rate_limit,
            max_idle=settings.throttle_max_idle,
        ),
    )
    dp.update.outer_middleware(LoggingMiddleware())
    dp.update.outer_middleware(TracingMiddleware())
    dp.update.outer_middleware(UpdatesMiddleware())
    dp.message.middleware(RetryMiddleware())
    register_error_handler(dp)
    bot = create_bot(settings.bot_token)

    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    if settings.webhook_url:
        await _run_webhook(settings, dp, bot, shutdown_event)
    else:
        await _run_polling(settings, dp, bot, shutdown_event)


if __name__ == "__main__":
    asyncio.run(main())
