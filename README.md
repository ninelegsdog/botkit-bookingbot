# botkit-bookingbot

Telegram bot for booking appointments with specialists.

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env  # fill in tokens
```

## Run

```bash
# Polling (dev)
python -m bot

# Webhook (prod)
python -m bot --webhook
```

## Test

```bash
pytest
```

## Deploy

```bash
docker compose up -d
```

## Бэкапы
Крон на VPS (ежедневно 04:00, retention 14 дней):
```
0 4 * * * AGE_RECIPIENT=age1... OFFSITE_TARGET=user@backup-host:/srv/backups /usr/local/bin/botkit-backup.sh BOTNAME
```
Восстановление:
```
botkit-restore.sh BOTNAME <db-name>.db ~/.secrets/keys/backup.txt [target-dir]
```
Скрипты: `~/bin/backup/{botkit-backup.sh,botkit-restore.sh}`.
