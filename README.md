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

## Development process

This project was built in an AI-native workflow. Implementation code was produced by
AI coding agents inside an agent harness I designed — requirements slots, instructions,
constraints and acceptance criteria that I defined up front.

My role:

- product requirements and user scenarios;
- task decomposition into independent engineering stages;
- context engineering: agent instructions, constraints, working rules;
- context-window management across iterations;
- the specification → generation → run → verify → fix loop;
- result validation, testing and code review;
- control over repository structure, configuration, documentation and reproducible startup.

Implementation code was generated with AI coding agents under human-led engineering control.

The full process, an `AGENTS.md` template and review checklists live in
[agentic-development-playbook](https://github.com/ninelegsdog).
