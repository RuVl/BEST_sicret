# BEST_sicret bot

Telegram-бот для СПб BEST: генерация внутренних документов (приказы), учёт
имущества/инвентаря и заявки на возмещение. Построен на **aiogram 3** +
**aiogram-dialog 2**, тексты — на русском, рантайм — **Python 3.12**.

Это один из сервисов монорепозитория (см. корневой `README.md`). Схема БД живёт в
общем пакете `best_db` (`packages/db`); бот держит свой engine/session и импортирует
модели оттуда.

## Запуск

```bash
# зависимости (uv) + общий пакет best_db editable
make install-bot                 # из корня репозитория

# заполнить конфиг
cp bot/.env.dist bot/.env        # затем отредактировать

# локально
cd bot && python3 run.py         # или: make run-bot

# postgres + redis для локальной разработки
make infra
```

## Конфигурация

Все настройки читаются через `pydantic-settings` в `bot/env.py` (группы
`TelegramConfig`/`PostgresConfig`/`RedisConfig`/`ProjectConfig`/`LoggerConfig`,
агрегированы в `GlobalSettings`). Шаблон — `bot/.env.dist`. Привилегированные ID:
`PRESIDENT_ID` (получает уведомления) и `TREASURER_ID` (доступ к `/add_equipment`).

## Линт и форматирование

```bash
cd bot && ruff check --fix && ruff format    # или репозиторно: make lint / make format
```

Архитектура слоёв (handlers → dialogs → includes/templates → database/docx) и
конвенции подробно описаны в корневом `CLAUDE.md`.
