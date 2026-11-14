# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Reply to the user in Russian.** This guide is in English, but all answers, explanations, and questions to the user must be in Russian. Code comments and user-facing strings are predominantly Russian too.

## Overview

Telegram bot for the SPb BEST student organization: internal documents (приказы), equipment, refund requests, and VPN (VLESS and AmneziaWG through a 3x-ui panel). **aiogram 3** + **aiogram-dialog 2**, **Python 3.12**.

- **`bot/`** — the bot. Own venv, `.env`/`dev.env`, `Dockerfile`, engine.
- **`members_sync/`** — daily sync of members from Google Sheets to Postgres. See `members_sync/ARCHITECTURE.md`.
- **`packages/db/`** — `best_db`, the **single owner of the Postgres schema**: all SQLAlchemy models and the **one** Alembic history. Each service installs it as an editable dependency and keeps its own engine/session.

## Commands

**Always prefer `make` targets over hand-rolled commands** (`cd bot && python run.py`, `cd packages/db && alembic …`, bare `docker compose …`/`uv run …`). Run `make help` for the full list.

```bash
make init                    # full bootstrap
make install                 # all venvs (or install-db, install-bot, install-sync)
make run-bot                 # bot locally + postgres/redis in docker
make dev-member who=@nick    # local LbgMember so /start opens the full menu (refuses when DEBUG=False)
make run-sync                # members_sync locally + postgres in docker
make run-sync-dry            # parse live data to JSON, no DB write
make up / down / build / ps  # full stack in docker
make migration m="message"   # new revision: Alembic lives in packages/db, NOT in bot/
make migrate                 # upgrade local DB (make migrate-docker, make downgrade [rev=-1])
make lint / format           # ruff
make test                    # both suites (make test-bot, make test-sync)
```

**Env files:** `.env` is for docker/podman (hosts = compose service names); `dev.env` holds local overrides (e.g. `POSTGRES_HOST=localhost`). Never read `*.env` files — use the matching `.env.dist` and the `env.py` code.

**Tooling:** `uv` for venvs and running, `uvx ruff@0.15.12` for lint/format, `uvx pre-commit` for hooks. Line length is **120**. Pre-commit runs ruff only; GitHub Actions run `make lint` and `make test` on every PR to `dev` and `main`.

## Architecture

### `bot/`

`run.py` builds the `Bot` + `Dispatcher`, registers middlewares then handlers, and starts polling. Registration order matters: **only the first matching handler runs**, and the dialogs router is included last.

**Layer flow:** `handlers/` → start an aiogram-dialog state machine → `dialogs/` → `includes/` → `database/` or `.docx` generation.

- **`handlers/`** — `commands.py` holds the only command, `/start`: it get-or-creates the `Person`, links it to an `LbgMember` by Telegram username, and starts the main menu. Everything else opens from menu buttons shown only to LBG members (`utils.access.current_member`).
- **`state_machines/`** — one `StatesGroup` per flow.
- **`dialogs/`** — `Dialog`/`Window` definitions, aggregated on `user_dialog_router` in `dialogs/user/__init__.py`. Unknown-state errors reset the stack.
- **`includes/templates/`** — **the core domain engine.** `create_context()` turns a JSON Schema (draft-07) into a tree of `BaseContext` subclasses (`ObjectContext`, `ArrayContext`, `PrimitiveContext`). Each node renders its view and keyboards, accepts typed input, and tracks required fields; `generate_context` produces the dict for `docxtpl`. Context objects are **pickled into Redis FSM state**: bump `BaseContext.__version__` when their shape changes.
- **Document templates** — `bot/resources/templates/<Name>.docx` + `<Name>.json` (JSON Schema with `question`, `short_description`). Adding a document needs no code change. Real templates are not in git; local runs use the fictional one from `resources/demo_templates/` via `TEMPLATES_DIR` in `dev.env`. Other schemas are in `resources/equipments/` and `resources/refunds/`.
- **`includes/vpn/`, `includes/awg/`** — VPN over the 3x-ui panel through the `py3xui` library (fork RuVl/py3xui, pinned to a tag). `vpn/panel.py` holds only bot decisions; `service.py` holds the domain operations; `AwgClient` maps panel errors to `AwgError` for the AmneziaWG dialogs.
- **`database/`** — async SQLAlchemy 2.0 + asyncpg. `database/main.py` has the bot's `engine` and `async_session`. Models live in `best_db.models`: import them from there. Queries are small async functions in `database/methods/<entity>/`.
- **`middlewares/`** — registered in `middlewares/main.py`. Localization (`L10nMw`, key `l10n`) is an outer middleware; then empty-callback dropping; then logging (`LoggingMw`, key `log`).
- **`includes/storage.py`** — `PickleRedisStorage` pickles FSM data; falls back to `MemoryStorage` when `USE_REDIS=False`.
- **`includes/fluent.py` + `l10n/`** — Fluent localization, `.ftl` files are auto-discovered.
- **`env.py`** — `pydantic-settings` groups on a `GlobalSettings` singleton, env names via `alias=`. `PRESIDENT_ID` and `TREASURER_ID` are notification fallbacks (`utils/board.py`).

### `members_sync/`

A pipeline: `sheets/` → `parsing/` (pure normalizers + issue collection) → `database/` → `sync/`. `run.py` runs `RUN_MODE=once` or `cron`. The sheet layout is data-driven via frozen `SheetSpec`/`ColumnDef` dataclasses.

### `packages/db/`

Single `Base` and one registry, so cross-service relationships work (e.g. `Person.lbg_member`). SQLAlchemy 2.0 style: `Mapped[T]`, `mapped_column(...)`, `comment=` on columns, `JSONB` for raw snapshots, timezone-aware `DateTime`.

## Code Style & Conventions

> **Read [CLEAN_CODE.md](CLEAN_CODE.md) before writing bot code.** It holds the binding rules: layering, aiogram-dialog do's and don'ts, repository and session rules, Fluent + MarkdownV2 pitfalls, what to test, and the pre-PR checklist.

Match the surrounding style and reuse existing helpers. Patterns in use:

- **Composite + Factory** — the templates engine; `get_formatter`/`get_validator` are `@lru_cache` factories.
- **Strategy** — `formatters.py`, `validators.py`, resolved by JSON Schema `type`/`format`.
- **Repository** — `database/methods/<entity>/`: **the caller owns the commit**.
- **Dependency injection via middlewares** — `l10n` and `log` come from `middleware_data`; don't construct them ad hoc.
- **Pipeline + pure functions** — `members_sync` normalizers **never raise**: they return `(value, error)` and raw values are always preserved.

Logging is `structlog`: `structlog.get_logger()`, prefer `await logger.ainfo(...)`. All I/O is async. Telegram parse mode is **MarkdownV2**: escape dynamic text via `utils.escape_mdv2`.

## Working agreements

- **Reply to the user in Russian.**
- **Prefer `make` targets** over hand-written commands.
- **Never read `*.env` files** — use the matching `.env.dist` template and the `env.py` code.
- **After each action, end your reply with a one-line summary of what you did, written as a Conventional-Commit message:** `type(scope): что сделал` in the imperative mood, matching this repo's history. Types: `feat`, `fix`, `refactor`, `style`, `docs`, `ci`, `test`, `chore`. Scopes: `bot`, `member_sync`, `db`, `settings`, `deps`, etc. Example: `docs(claude): переписал гайд по проект, описал make цели`. This is a recap of the work performed — **not** an instruction to create a git commit (only commit when the user explicitly asks).
