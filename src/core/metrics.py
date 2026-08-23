from __future__ import annotations

import logging
from typing import Any

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

logger = logging.getLogger(__name__)

UPDATES_TOTAL = Counter(
    "bot_updates_total",
    "Total updates received from Telegram",
    ["type"],
)
ERRORS_TOTAL = Counter(
    "bot_errors_total",
    "Total errors handled by the global error handler",
    ["error_type"],
)


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
    return web.Response(text="ok")


async def metrics(request: web.Request) -> web.Response:
    return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


def create_metrics_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/metrics", metrics)
    return app


async def start_metrics_server(port: int) -> web.AppRunner:
    runner = web.AppRunner(create_metrics_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Metrics server started on port %s", port)
    return runner
