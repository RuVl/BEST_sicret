# BEST_sicret

Монорепозиторий сервисов СПб BEST: Telegram-бот для внутренних документов, имущества, возмещений и VPN и сервис
синхронизации участников из Google Sheets в Postgres.

| Каталог               | Что это                                                            |
|-----------------------|--------------------------------------------------------------------|
| `bot/`                | Telegram-бот на aiogram 3 и aiogram-dialog 2 ([README](bot/README.md)) |
| `members_sync/`       | Ежедневная синхронизация участников ([README](members_sync/README.md)) |
| `packages/db/`        | `best_db`: все модели и единый alembic ([README](packages/db/README.md)) |
| `postgres/`, `redis/` | Конфиги `.env` для docker-compose                                  |

Каждый сервис - отдельный проект со своим venv и engine, общая только схема БД.

## Быстрый старт

Нужны `uv` и `docker compose`.

```bash
make init       # с нуля: проверка зависимостей, .env, venv, хуки, инфраструктура, миграции
make run-bot    # бот локально, postgres и redis в docker
make test       # тесты бота и members_sync
make lint       # проверка кода
make help       # все команды
```

Правила кода - в [CLEAN_CODE.md](CLEAN_CODE.md), обзор архитектуры - в [CLAUDE.md](CLAUDE.md).
