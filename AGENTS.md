# AGENTS.md

## Role
User = product owner. Agent = инженер + devops + tech lead. Проактивен: решает и делает, не спрашивает.

## Tech Stack
- Python 3.13, aiogram 3.30+
- SQLite WAL + SQLAlchemy 2.0 async
- Redis FSM
- YooKassa payments + Mock provider
- pytest, ruff, mypy strict

## Conventions
- Line ≤120, PEP8, type hints
- Conventional Commits
- Tests before commit
- `ruff check .` + `mypy src/` must pass

## Security
- Docker: user 1001:1001, read_only, cap_drop ALL
- No secrets in code
- `.env` for secrets
