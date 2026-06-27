# BEST_sicret

Монорепозиторий сервисов СПб BEST. Включает Telegram-бота для работы с внутренними
документами и сервис синхронизации участников из Google Sheets в Postgres.

## Структура

| Каталог               | Что это                                                                                                        |
|-----------------------|----------------------------------------------------------------------------------------------------------------|
| `bot/`                | Telegram-бот (aiogram 3 + aiogram-dialog 2): приказы, имущество, возмещения. См. `bot/README.md`.              |
| `members_sync/`       | Сервис ежедневной синхронизации участников из Google Sheets. См. `members_sync/README.md` и `ARCHITECTURE.md`. |
| `packages/db/`        | `best_db` — единственный владелец схемы Postgres: все модели + единый alembic. См. `packages/db/README.md`.    |
| `postgres/`, `redis/` | Конфиги (`.env`) сервисов БД и кэша для docker-compose.                                                        |

Каждый сервис — отдельный проект (своя venv/зависимости, свой engine), общая только
схема БД (пакет `best_db`, подключается как зависимость). Единые команды разработки
собраны в корневом `Makefile` (`make help`).

## Быстрый старт

```bash
# Подготовить окружение с нуля (проверка зависимостей, .env, venv, хуки, миграции)
make init

# Весь стек (bot + members_sync + postgres + redis) в контейнерах
make up                  # = docker compose up -d --build

# Только postgres + redis для локальной разработки
make infra

# Локальный запуск сервисов (нужны заполненные .env, копируются из .env.dist)
make run-bot
make run-sync

# Миграции (единый alembic в packages/db)
make migration m="..."   # новая ревизия
make migrate             # применить локально
make migrate-docker      # в сети compose

# Качество кода и тесты
make lint
make format
make test                # юнит-тесты members_sync
```

`make help` — полный список целей.

Подробные инструкции и архитектура — в README конкретного сервиса.