from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str = ""
    admin_password: str = ""
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
