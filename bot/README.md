# BEST_sicret bot

Telegram-бот для СПб BEST: генерация внутренних документов (приказы), учёт
имущества/инвентаря и заявки на возмещение. Построен на **aiogram 3** +
**aiogram-dialog 2**, тексты — на русском, рантайм — **Python 3.12**.

Это один из сервисов монорепозитория (см. корневой `README.md`). Схема БД живёт в
общем пакете `best_db` (`packages/db`); бот держит свой engine/session и импортирует
модели оттуда.

## Запуск

Команды запускаются через корневой `Makefile` (`make help` — полный список); ручные
`cd bot && python run.py` / `docker compose …` не нужны.

```bash
# зависимости (uv) + общий пакет best_db editable
make install-bot                 # из корня репозитория

# создать конфиги из шаблонов: .env (docker) и dev.env (локальный запуск)
make env                         # затем заполнить bot/.env и bot/dev.env

# локальный запуск (поднимет postgres/redis в docker, стартует бота на dev.env)
make run-bot

# только postgres + redis для локальной разработки
make infra
```

## Конфигурация

Все настройки читаются через `pydantic-settings` в `bot/env.py` (группы
`TelegramConfig`/`PostgresConfig`/`RedisConfig`/`ProjectConfig`/`LoggerConfig`,
агрегированы в `GlobalSettings`). Шаблон — `bot/.env.dist`. Привилегированные ID —
запасные получатели уведомлений, если роль не нашлась в таблице участников:
`PRESIDENT_ID` и `TREASURER_ID`.

## Линт и форматирование

```bash
make lint        # ruff check + проверка форматирования (без правок)
make format      # ruff check --fix + ruff format
```

Архитектура слоёв (handlers → dialogs → includes/templates → database/docx) и
конвенции подробно описаны в корневом `CLAUDE.md`.
