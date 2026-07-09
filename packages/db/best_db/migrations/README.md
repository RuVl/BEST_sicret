Migrations (best_db, единый alembic)
---

Alembic уже инициализирован (async-шаблон). Это единственная история схемы для всех
сервисов (`bot`, `members_sync`); файлы в `versions/` **коммитятся**. Конфиг —
`packages/db/alembic.ini`, URL собирается из `POSTGRES_*` в `env.py`.

Команды — через корневой `Makefile` (ручной `alembic …` не нужен):

1. Сгенерировать миграцию по изменениям моделей:
   ```shell
   make migration m="message"
   ```
2. Проверить сгенерированный файл и применить:
   ```shell
   make migrate
   ```
3. В сети docker-compose (host=postgres):
   ```shell
   make migrate-docker
   ```
4. Откатить при необходимости:
   ```shell
   make downgrade rev=-1
   ```

> Нужны переменные окружения `POSTGRES_HOST/PORT/USER/PASSWORD/DB`
> (для dev-стека `POSTGRES_HOST=localhost`).
