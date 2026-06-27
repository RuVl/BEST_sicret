Migrations (best_db, единый alembic)
---

Alembic уже инициализирован (async-шаблон). Это единственная история схемы для всех
сервисов (`bot`, `members_sync`); файлы в `versions/` **коммитятся**. Конфиг —
`packages/db/alembic.ini`, URL собирается из `POSTGRES_*` в `env.py`.

Из каталога `packages/db/` (или через корневой `Makefile`):

1. Сгенерировать миграцию по изменениям моделей:
   ```shell
   alembic revision --autogenerate -m 'message'   # make migration m="message"
   ```
2. Проверить сгенерированный файл и применить:
   ```shell
   alembic upgrade head                            # make migrate
   ```
3. В сети docker-compose (host=postgres):
   ```shell
   docker compose run --rm db_migrate              # make migrate-docker
   ```

> Нужны переменные окружения `POSTGRES_HOST/PORT/USER/PASSWORD/DB`
> (для dev-стека `POSTGRES_HOST=localhost`).
