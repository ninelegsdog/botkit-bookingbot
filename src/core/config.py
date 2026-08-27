from typing import Annotated

from pydantic import model_validator
from pydantic_settings import BaseSettings


def parse_admin_ids(v: str | None) -> list[int]:
    if not v:
        return []
    return [int(x.strip()) for x in v.split(",") if x.strip()]


class Settings(BaseSettings):
    bot_token: str = ""
    admin_password: str = ""
    admin_ids: Annotated[list[int], parse_admin_ids] = []
    database_url: str = "sqlite+aiosqlite:///app.db"
    redis_url: str | None = None
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    webhook_secret_token: str = ""
    webhook_url: str = ""
    sentry_dsn: str = ""
    metrics_port: int = 8080
    timezone: str = "Europe/Moscow"
    throttle_rate_limit: float = 0.5
    throttle_max_idle: float = 60.0

    model_config = {"env_prefix": "BOTKIT__", "env_file": ".env"}

    @model_validator(mode="after")
    def validate_required(self) -> "Settings":
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN is not set")
        if not self.admin_password:
            raise RuntimeError("ADMIN_PASSWORD is not set")
        if not self.admin_ids:
            raise RuntimeError("ADMIN_IDS is not set")
        return self
