# members_sync

Сервис ежедневной синхронизации участников BEST из Google Sheets в Postgres.
Google-таблица — единственный источник истины. Архитектура и принципы устойчивости
описаны в [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Что делает

1. Читает три листа таблицы (раскладки A и B определяются по названию листа).
2. Сопоставляет колонки **по тексту заголовка** (устойчиво к перестановке/переименованию).
3. Собирает участников (2 строки = 1 человек), определяет статус по секции.
4. Делает upsert в таблицу `lbg_members` по ключу: best-email → fallback ФИО.
5. Кого нет в таблице — помечает `inactive` (не удаляет).
6. Пишет человекочитаемые ошибки парсинга **заметками к ячейкам** (опционально).
7. Формирует markdown-отчёт о прогоне и JSON-дамп.

## Конфигурация

Скопируйте `.env.dist` → `.env` и заполните. Ключевое:

| Переменная                                | Назначение                                                                      |
|-------------------------------------------|---------------------------------------------------------------------------------|
| `SPREADSHEET_KEY`                         | ключ Google-таблицы                                                             |
| `API_CREDENTIALS_FILE`                    | путь к `service_account.json`                                                   |
| `WRITE_SHEET_NOTES`                       | писать ли заметки об ошибках в таблицу (нужно право редактирования)             |
| `RUN_MODE`                                | `once` (один прогон) или `cron` (по расписанию)                                 |
| `CRON_HOUR`/`CRON_MINUTE`/`CRON_TIMEZONE` | расписание (по умолчанию 03:00 Europe/Moscow)                                   |
| `AUTO_CREATE_SCHEMA`                      | создавать таблицу на старте (`create_all`); отключите при использовании alembic |
| `POSTGRES_*`                              | подключение к БД (как у бота)                                                   |
| `LOG_*`                                   | три приёмника логов (stdout/файл/markdown)                                      |

Логи:
- stdout контейнера — все уровни;
- `logs/members_sync.log` — все уровни (ротация);
- `logs/warnings.md` — только warning/error;
- `last_sync_report.md` — структурированный отчёт о последнем прогоне.

## Запуск

Сервис — отдельный проект (своя venv) и зависит от общего пакета `best_db`
(`packages/db`). Зависимости описаны в `pyproject.toml` (`uv`), общий пакет
подключён как editable (`[tool.uv.sources] best-db = ../packages/db`).

```bash
# из корня репозитория — поставить best_db + зависимости сервиса
make install-sync

# один прогон (RUN_MODE из .env)
cd members_sync && python3 run.py        # или: make run-sync
```

В составе docker-compose (контейнер живёт постоянно, синхронизация по расписанию
`RUN_MODE=cron`). Общий пакет приезжает в образ через named build context
(`build.additional_contexts: { database: ./packages/db }`):

```bash
docker compose up -d --build members_sync
```

## Миграции

Схема — единый alembic в общем пакете `best_db` (`packages/db`), он же владелец всех
таблиц для бота и `members_sync`. Команды миграций запускаются оттуда (или через
`make migrate` / `make migration m="..."`); в dev можно создать схему на старте
(`AUTO_CREATE_SCHEMA=True`, `create_all`). См. `packages/db/README.md`.

## Структура

```
sheets/    — доступ к Google Sheets, маппинг колонок, чтение записей, заметки
parsing/   — нормализаторы, сбор ParsedMember, ошибки
database/  — свой engine + методы upsert/deactivate (модель LbgMember и alembic — в best_db)
sync/      — оркестратор + отчёт
tests/     — юнит-тесты нормализаторов и пайплайна (make test)
run.py     — точка входа (once/cron)
```
