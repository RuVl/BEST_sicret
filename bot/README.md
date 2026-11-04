# BEST_sicret bot

Telegram-бот СПб BEST: приказы, учёт имущества, заявки на возмещение, VPN (VLESS и AmneziaWG через панель 3x-ui).
aiogram 3 + aiogram-dialog 2, Python 3.12. Схема БД живёт в общем пакете `best_db` (`packages/db`).

## Запуск

```bash
make install-bot   # зависимости
make env           # создать .env (docker) и dev.env (локально), затем заполнить bot/.env и bot/dev.env
make run-bot       # бот локально, postgres и redis в docker
make test-bot      # тесты
```

## Конфигурация

Настройки читает `bot/env.py` через `pydantic-settings`, шаблон - `bot/.env.dist`. `PRESIDENT_ID` и `TREASURER_ID` -
запасные получатели уведомлений, если роль не нашлась в таблице участников.

Архитектура - в корневом [CLAUDE.md](../CLAUDE.md), правила кода - в [CLEAN_CODE.md](../CLEAN_CODE.md).
