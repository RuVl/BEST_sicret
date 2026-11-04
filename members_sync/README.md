# members_sync

Ежедневная синхронизация участников BEST из Google Sheets в Postgres. Таблица - единственный источник истины. Как это
устроено - в [ARCHITECTURE.md](ARCHITECTURE.md).

Сервис читает три листа, сопоставляет колонки по заголовкам, собирает участников (2 строки = 1 человек) и делает upsert
в `lbg_members`. Кого нет в таблице, он помечает неактивным, но не удаляет. Ошибки парсинга может писать заметками к
ячейкам, после прогона пишет отчёт и JSON-дамп.

## Запуск

```bash
make install-sync
make env            # создать .env (docker) и dev.env (локально), затем заполнить
make run-sync       # один прогон локально, postgres в docker
make run-sync-dry   # парсинг боевых данных в JSON без записи в БД, postgres не нужен
make test-sync      # тесты
make up             # весь стек в docker, синхронизация по расписанию
```

## Конфигурация

| Переменная                                | Назначение                                                            |
|-------------------------------------------|-----------------------------------------------------------------------|
| `SPREADSHEET_KEY`                         | ключ Google-таблицы                                                   |
| `API_CREDENTIALS_FILE`                    | путь к `service_account.json`                                         |
| `WRITE_SHEET_NOTES`                       | писать заметки об ошибках в таблицу (нужно право редактирования)      |
| `RUN_MODE`                                | `once` - один прогон, `cron` - по расписанию                          |
| `CRON_HOUR`/`CRON_MINUTE`/`CRON_TIMEZONE` | расписание, по умолчанию 03:00 Europe/Moscow                          |
| `AUTO_CREATE_SCHEMA`                      | создавать таблицу на старте; отключите, если схему накатывает alembic |
| `POSTGRES_*`                              | подключение к БД                                                      |
| `LOG_*`                                   | приёмники логов                                                       |

Логи и отчёты: `logs/members_sync.log` (все уровни, ротация), `logs/warnings.md` (warning и error),
`last_sync_report.md` (последний прогон).
