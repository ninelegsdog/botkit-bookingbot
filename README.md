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
