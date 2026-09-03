from __future__ import annotations

import logging
from typing import Any

from aiohttp import web
from botkit_core.metrics import (
    BOTKIT_ERRORS_TOTAL,
    BOTKIT_UPDATES_TOTAL,
)
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from src.core.config import Settings
from src.core.database import Database

try:
    from botkit_core import __version__ as _core_version
except ImportError:
    _core_version = "0.0.0"

logger = logging.getLogger(__name__)

_db: Database | None = None


def _get_db() -> Database:
    global _db
    if _db is None:
        _db = Database(Settings().database_url)
    return _db

UPDATES_TOTAL = BOTKIT_UPDATES_TOTAL
ERRORS_TOTAL = BOTKIT_ERRORS_TOTAL


class UpdatesMiddleware:
    """Counts every incoming update."""

    async def __call__(
        self,
        handler: Any,
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        UPDATES_TOTAL.labels(type=type(event).__name__.lower()).inc()
        return await handler(event, data)


async def health(request: web.Request) -> web.Response:
    accept = request.headers.get("Accept", "")
    if "application/json" in accept:
        # JSON with version for version-drift guard
        try:
            db = _get_db()
            async with db.session() as session:
                await session.execute(text("SELECT 1"))
            return web.json_response({"status": "ok", "version": _core_version})
        except Exception:
            return web.json_response({"status": "db unavailable", "version": _core_version}, status=500)
    # Text fallback for old probes / curl
    try:
        db = _get_db()
        async with db.session() as session:
            await session.execute(text("SELECT 1"))
        return web.Response(status=200, text="ok")
    except Exception:
        return web.Response(status=500, text="db unavailable")


async def version(request: web.Request) -> web.Response:
    return web.json_response({"version": _core_version, "service": "botkit"})


async def metrics(request: web.Request) -> web.Response:
    return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


def create_metrics_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/version", version)
    app.router.add_get("/metrics", metrics)
    return app


async def start_metrics_server(port: int) -> web.AppRunner:
    runner = web.AppRunner(create_metrics_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Metrics server started on port %s", port)
    return runner
