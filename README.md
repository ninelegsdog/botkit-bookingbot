# BotKit Booking

Telegram-бот записи к специалистам с онлайн-оплатой брони.

Живой бот: @SaasBookingKitBot · часть портфолио из 9 Telegram-ботов на Python.

## Возможности

- Запись к специалистам: услуги, слоты, расписание
- Онлайн-оплата брони (ЮKassa)
- Личный кабинет клиента: «Мои записи», перенос и отмена
- Напоминания о визите
- Админка в чате: услуги, расписание, заявки, статистика
- Антифлуд, `/metrics`, Sentry
- Docker, webhook (prod) / polling (dev)

## Стек

- Python 3.12+
- aiogram 3.x
- SQLAlchemy 2 (async) + SQLite (WAL) / PostgreSQL
- Redis (FSM, антифлуд)
- ЮKassa — платежи
- Prometheus `/metrics`
- Sentry
- Docker, webhook (prod) / polling (dev)

## Быстрый старт

```bash
cp .env.example .env      # заполнить BOTKIT__BOT_TOKEN и BOTKIT__ADMIN_IDS
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
python -m bot
```

## Переменные окружения

Ключи задаются с префиксом `BOTKIT__`: `BOTKIT__BOT_TOKEN`, `BOTKIT__ADMIN_IDS`,
`BOTKIT__ADMIN_PASSWORD`, `BOTKIT__DATABASE_URL`, `BOTKIT__REDIS_URL`,
`BOTKIT__YOOKASSA_SHOP_ID`, `BOTKIT__YOOKASSA_SECRET_KEY`,
`BOTKIT__WEBHOOK_SECRET_TOKEN`, `BOTKIT__WEBHOOK_URL`, `BOTKIT__SENTRY_DSN`,
`BOTKIT__METRICS_PORT`, `BOTKIT__TIMEZONE`, `BOTKIT__THROTTLE_RATE_LIMIT`,
`BOTKIT__THROTTLE_MAX_IDLE`.

Секреты не хранятся в git: `.env` в `.gitignore`, в CI включён gitleaks-гейт.

## Тесты

```bash
pytest
```

Оффлайн-набор (без сети и Telegram) — `pytest -m no_req`. Гейт покрытия —
`--cov-fail-under=80` в `pyproject.toml`; детали и уровни пирамиды —
в [README-testing.md](README-testing.md).

## Бэкапы

Бэкапы и восстановление — общий контур на проде (systemd-таймеры, offsite restic,
один общий Redis на все боты), а не отдельный скрипт внутри репозитория.
Актуальная процедура и оговорки — в
[`botkit-monitoring/ops/backup/RESTORE.md`](https://github.com/ninelegsdog/botkit-monitoring/blob/main/ops/backup/RESTORE.md).

```bash
# проверка бэкапа этого бота (ничего не меняет)
/root/restore_test.sh botkit-bookingbot
```

## Development process

Проект создан в AI-native процессе разработки: код производили AI coding-агенты
в настроенном мной agent harness — то есть по слотам требований, инструкций, ограничений
и критериев приёмки, которые я задал заранее.

Моя роль в проекте:

- продуктовая постановка и пользовательские сценарии;
- декомпозиция задачи на самостоятельные инженерные этапы;
- context engineering: инструкции, ограничения и рабочие правила для агентов;
- управление контекстным окном между итерациями;
- цикл «спецификация → генерация → запуск → проверка → исправление»;
- валидация результата, тестирование, ревью;
- контроль структуры репозитория, конфигурации, документации и воспроизводимости запуска.

Implementation code was generated with AI coding agents under human-led engineering control.

Полное описание процесса, шаблон `AGENTS.md` и чек-листы ревью AI-кода и секретов —
в репозитории [agentic-development-playbook](https://github.com/ninelegsdog/agentic-development-playbook).

## Лицензия

MIT — см. [LICENSE](LICENSE).

## Статус

Проект работает в продакшене (webhook, TLS, health-check). Состояние: **production**.
