# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Reply to the user in Russian.** This guide is written in English, but all answers, explanations, and questions to the user must be in Russian — code, comments, and user-facing strings in this project are predominantly Russian.

## Overview

Telegram bot for the SPb BEST student organization that generates internal documents (приказы / orders) and tracks equipment/inventory and refund requests. Built on **aiogram 3** + **aiogram-dialog 2**. Code, comments, and user-facing strings are predominantly **Russian**. Target runtime is **Python 3.12**.

The repo is a small multi-service monorepo:

- **`bot/`** — the Telegram bot (this document's main subject). Own venv, `.env`/`dev.env`, `Dockerfile`, engine.
- **`members_sync/`** — a standalone service that syncs BEST members from Google Sheets into Postgres once a day. Own venv, `env`, `Dockerfile`, and engine. See `members_sync/ARCHITECTURE.md` and `members_sync/README.md`.
- **`packages/db/`** — `best_db`, the **single owner of the Postgres schema** for both services: all SQLAlchemy models (`best_db.models`) and the **one** Alembic history (`best_db/migrations`) live here. Each service installs it as an editable dependency and keeps its own engine/session. See `packages/db/README.md`.

Each service has its own dependencies and venv; the root `Makefile` provides the unified install/lint/test/migrate/run/up flow.

## Commands — use the Makefile

**Always prefer `make` targets over hand-rolled commands.** Do **not** hand-write `cd bot && python run.py`, `cd packages/db && alembic …`, or bare `docker compose …`/`uv run …` — the `Makefile` already wraps all of these in a cross-platform way (everything runs through `uv` / `uvx` / `docker compose`, so no `grep`/`sed`/`find` tricks are needed). Run `make help` for the full list.

```bash
# Environment setup
make init          # full bootstrap: check-deps → env → install → pre-commit → infra → migrate
make check-deps    # verify uv and docker compose are available
make env           # create .env (docker) and dev.env (local) from *.dist where missing

# Install dependencies (per-service venvs)
make install       # all venvs (db + bot + sync)
make install-db    # best_db venv (packages/db)
make install-bot   # bot venv (+ best_db editable)
make install-sync  # members_sync venv (+ best_db editable, + dev: pytest)

# Run
make infra         # postgres + redis only, in docker (ports exposed to host)
make infra-down    # stop local infrastructure
make run-bot       # bot locally (dev.env) + postgres/redis in docker
make run-sync      # members_sync locally (dev.env) + postgres in docker
make run-sync-dry  # members_sync dry-run: parse live data to JSON, no DB write (no postgres needed)
make up            # full stack in docker (bot + members_sync + postgres + redis)
make down          # stop the stack
make build         # rebuild images
make ps            # container status

# Migrations — single Alembic in packages/db (NOT in bot/)
make migration m="message"   # new autogenerate revision
make migrate                 # upgrade local DB to head
make downgrade [rev=-1]      # downgrade (default one step back)
make migrate-docker          # apply migrations inside docker (db_migrate service)

# Logs
make logs          # whole stack (follow)
make logs-bot      # bot only
make logs-db       # postgres
make logs-redis    # redis

# Database dump / restore (connects via unix socket inside container, no password)
make db-dump [DUMP=backups/dump.sql]    # dump DB to file
make db-restore DUMP=backups/x.sql      # restore DB from file
make psql                               # interactive psql in container

# Redis
make redis-flush   # FLUSHALL the whole cache

# Code quality
make pre-commit-install   # install git hooks
make pre-commit           # run pre-commit on all files
make lint                 # ruff check + format --check (no edits)
make format               # ruff check --fix + ruff format
make test                 # members_sync unit tests (pytest)

# Cleanup
make clean         # remove caches (__pycache__, .ruff_cache, .mypy_cache, .pytest_cache)
make clean-venv    # remove all per-service .venv dirs (restore with make install)
make nuke          # stop stack AND erase data (postgres/redis volumes)
```

**Env files:** `.env` is for running in docker/podman (hosts = compose service names); `dev.env` holds local-run overrides (e.g. `POSTGRES_HOST=localhost`) layered on top via `uv run --env-file dev.env`. Never read `*.env` files — use the matching `.env.dist` template plus the `env.py` code instead.

**Tooling:** `uv` for venvs/running, `uvx ruff@0.15.12` for lint/format, `uvx pre-commit` for hooks. Line length is **120** (`.editorconfig`, ruff). mypy is configured in `.pre-commit-config.yaml` but currently commented out. Only `members_sync/` has a test suite (`make test`); the bot has none, and root-level `test*.py` are throwaway scratch scripts.

## Architecture

### `bot/`

`run.py` builds the `Bot` + `Dispatcher`, registers middlewares then handlers, and starts polling. Registration order matters — **only the first matching handler runs**, and the dialogs router is included last.

**Layer flow:** `handlers/` (command entrypoints) → start an aiogram-dialog state machine → `dialogs/` (windows + widgets) → `includes/templates/` (domain logic) → `database/` or `.docx` generation.

- **`handlers/`** — `register_handlers` wires `commands.router` and a dialogs router; `debug.router` is added only when `DEBUG`. `commands.py` holds the bot's **only** command, `/start`: it get-or-creates the `Person`, links it to an `LbgMember` by Telegram username, and starts the main-menu dialog (`ViewProfile.VIEW`, `StartMode.RESET_STACK`). Everything else — приказы, заявки, рефанды, имущество, VPN — opens from menu buttons that are shown only to LBG members (`utils.access.current_member`), so there is no command that bypasses the check.

- **`state_machines/`** — `StatesGroup` definitions (one per flow: templates, refund, apply_eq, add_eq, inventory). Imported by both handlers and dialogs.

- **`dialogs/`** — aiogram-dialog `Dialog`/`Window` definitions. `dialogs/user/__init__.py` aggregates every dialog onto `user_dialog_router`. Unknown-state/intent errors reset the stack (`dialogs/__init__.py`).

- **`includes/templates/`** — **the core domain engine.** A JSON Schema (draft-07) describing a document is turned into a tree of `BaseContext` subclasses (`ObjectContext`, `ArrayContext`, `PrimitiveContext`) via `create_context()`. The context tree is what the user navigates: each node renders its own view text (`render_view`) and keyboards (`render_data_kb` / `render_action_kb`), accepts typed input on primitives, tracks required-field completion (`filled_required` / `can_generate`), and finally produces a Jinja-style dict (`generate_context`) fed to `docxtpl`. `formatters.py` and `validators.py` are looked up by JSON Schema `type`/`format` (e.g. `date`). Context objects are **pickled into Redis FSM state**, so `BaseContext.__version__` must be bumped when their shape changes.

- **Document templates** live in `bot/resources/templates/` as paired files: `<Name>.docx` (docxtpl template) + `<Name>.json` (JSON Schema with extra UI keys `question`, `short_description`). `get_available_templates()` only lists names that have both. Adding a new document = drop in a matching `.docx` + `.json`, no code change. Other schemas live in `resources/equipments/` and `resources/refunds/`.

- **`database/`** — async SQLAlchemy 2.0 + asyncpg. `database/main.py` exposes the bot's own `engine` and `async_session` sessionmaker. The **models themselves live in `packages/db` (`best_db.models`)** — `bot/database/models/__init__.py` is a compatibility re-export so existing `database.models` imports keep working. Query/command helpers live under `database/methods/<entity>/` as small single-purpose async functions taking an `AsyncSession`.

- **`middlewares/`** — registered in `middlewares/main.py`. Order matters: localization (`L10nMw`, key `l10n`) is an outer middleware so other middlewares/handlers can use it; then empty-callback dropping; then logging (`LoggingMw`, key `log`).

- **`includes/storage.py`** — `PickleRedisStorage` overrides aiogram's `RedisStorage` to pickle FSM `data` (needed because dialog data holds `BaseContext` objects, not just JSON). Falls back to `MemoryStorage` when `USE_REDIS=False`.

- **`includes/fluent.py` + `l10n/`** — Fluent localization. `.ftl` files under `l10n/<locale>/` (currently only `ru`) are auto-discovered. Use `l10n.format_value(key, args=...)` for all user text.

- **`env.py`** — config via **`pydantic-settings`**: nested `BaseModel` groups (`TelegramConfig`, `PostgresConfig`, `RedisConfig`, `ProjectConfig`, `LoggerConfig`) aggregated on a `GlobalSettings(BaseSettings)` singleton. Field names map to env vars via `alias=` (e.g. token is `TG_API_TOKEN`). Two privileged Telegram user IDs are notification fallbacks when the board role can't be resolved from the members table (`utils/board.py`): `PRESIDENT_ID` and `TREASURER_ID`.

### `members_sync/`

A **pipeline**: `sheets/` (Google Sheets I/O, fuzzy column mapping, record reading) → `parsing/` (pure normalizers + issue collection) → `database/` (async upsert/deactivate) → `sync/` (orchestrator + markdown report). `run.py` runs `RUN_MODE=once` (single pass for an external scheduler) or `RUN_MODE=cron` (long-lived container, apscheduler). The sheet layout is data-driven via frozen `SheetSpec`/`ColumnDef` dataclasses — no hardcoded column indices. `env.py` uses the nested-`BaseSettings` section pattern (`GoogleConfig`/`SyncConfig`/`RunConfig`/`PostgresConfig`/`LoggerConfig` on a `Settings` instance, re-exported as `GoogleKeys`/`SyncKeys`/… for `XxxKeys.FIELD` call sites).

### `packages/db/`

`best_db` owns the schema. Single `Base(AsyncAttrs, DeclarativeBase)` and one registry, so cross-service relationships work (e.g. `Person.lbg_member` is an optional one-to-one link to a synced `LbgMember`). Models use SQLAlchemy **2.0** style: `Mapped[T]` type hints + `mapped_column(...)`, `relationship(..., back_populates=...)`, `comment=` on columns (preserved into migrations), `JSONB` for raw snapshots, timezone-aware `DateTime` with `server_default=func.now()`. One Alembic history under `best_db/migrations/`; its `env.py` reads `POSTGRES_*` env vars directly and supports async.

## Code Style & Conventions

> **Read [CLEAN_CODE.md](CLEAN_CODE.md) before writing bot code.** It holds this repo's binding rules — layering, aiogram-dialog do's and don'ts (self-sufficient getters, no per-dialog access middleware, where middleware data is and isn't injected), repository/session rules, Fluent + MarkdownV2 pitfalls, and the pre-PR checklist.

The codebase is small, async-first, and intentionally pattern-driven. Match the surrounding style; reuse existing utilities and helpers before writing new code.

**Design patterns already in use** (name and follow them):

- **Composite + Factory** — the templates engine (`bot/includes/templates/`). `create_context()` builds a polymorphic `BaseContext` tree (`PrimitiveContext` leaves, `ObjectContext`/`ArrayContext` composites); `get_formatter`/`get_validator` are `@lru_cache` factories.
- **Strategy** — `formatters.py` / `validators.py` define abstract `Formatter`/`Validator` bases, resolved at runtime by JSON Schema `type`/`format`.
- **Repository** — `bot/database/methods/<entity>/` and `members_sync/database/methods/`: small single-purpose `async` functions that take an `AsyncSession` and contain the queries. **The caller owns the commit** (`async with async_session() as session: … await session.commit()`), keep it that way.
- **Dependency injection via middlewares** — `l10n` and `log` are injected into `middleware_data` and pulled out by handlers/dialog getters; don't construct them ad hoc. Middlewares are cross-cutting and registered once in `bot/middlewares/main.py` — never add one just to gate a single dialog (see CLEAN_CODE.md §2.2).
- **Pipeline + pure functions** — `members_sync` normalizers are pure and **never raise**: they return `(value, error)` tuples and an `IssueCollector` aggregates problems while the row still gets ingested (raw values are always preserved). Keep this resilience: don't lose raw input.

**Clean code:**

- One responsibility per module/file (`formatters.py` only formatters, one method per file under `methods/<entity>/`).
- Comments explain **why**, not what; section dividers (`# === … ===`) are fine. Keep comments/docstrings/user strings in **Russian**.
- Bump `BaseContext.__version__` whenever the shape of pickled context objects changes (they live in Redis FSM state).
- Avoid circular imports with lazy imports inside functions and `TYPE_CHECKING` guards (see `includes/templates/main.py`).

**Type hints:** annotate everything. Use modern unions (`str | None`, not `Optional`), `Literal[...]` for finite choices, and generics (`list[Category]`, `async_sessionmaker[AsyncSession]`). Use Pydantic `BaseModel`/`BaseSettings` for config and `@dataclass` for plain data carriers (`ParsedMember`, `SheetSpec`, `ParseIssue`).

**Naming:** PascalCase classes, snake_case functions/variables, CONSTANT_CASE for class-level action constants (`BACK_ACTION`, `ADD_ITEM`), `_`-prefixed names for privates.

**Async:** all I/O (DB, Telegram, Sheets) is async. Open sessions with `async with async_session() as session:`. Logging is `structlog` — get a logger via `structlog.get_logger()` and prefer the async methods (`await logger.ainfo(...)`, `bind(user_id=…)`).

**Other conventions:** Telegram parse mode is **MarkdownV2** — escape user-supplied/dynamic text via `utils.escape_mdv2` before sending (context classes escape `title`/`description` in `BaseContext.__init__`). Fuzzy member search uses `fuzzywuzzy` (`utils.fuzzy_search_bests`).

## Working agreements

- **Reply to the user in Russian.**
- **Prefer `make` targets** over hand-written commands (see "Commands — use the Makefile").
- **Never read `*.env` files** — use the matching `.env.dist` template and the `env.py` code.
- **After each action, end your reply with a one-line summary of what you did, written as a Conventional-Commit message:** `type(scope): что сделал` in the imperative mood, matching this repo's history. Types: `feat`, `fix`, `refactor`, `style`, `docs`, `ci`, `test`, `chore`. Scopes: `bot`, `member_sync`, `db`, `settings`, `deps`, etc. Example: `docs(claude): переписал гайд по проект, описал make цели`. This is a recap of the work performed — **not** an instruction to create a git commit (only commit when the user explicitly asks).
