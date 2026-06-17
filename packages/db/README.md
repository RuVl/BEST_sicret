# best_db — общая схема БД

Единственный владелец таблиц Postgres для всех сервисов SPb BEST (`bot`,
`members_sync`). Здесь живут **все модели SQLAlchemy** (`best_db.models`) и
**единый alembic** (`best_db/migrations`). Сервисы импортируют модели отсюда, но
держат **собственный** engine/sessionmaker — общими являются только определения
таблиц и единый `Base` (один registry, чтобы работали связи между моделями
разных сервисов, например `Person.lbg_member`).

```
packages/db/
├── pyproject.toml            # пакет best-db (зависимости: SQLAlchemy, asyncpg, alembic)
├── alembic.ini               # единая конфигурация миграций
├── Dockerfile                # образ для разового прогона миграций (db_migrate)
└── best_db/
    ├── models/               # Base + все таблицы (Person, …, LbgMember)
    └── migrations/           # единая история alembic (versions/ — под git)
```

## Установка (локально)

В venv каждого сервиса:

```bash
pip install -e packages/db        # из корня репозитория
# или: make install-bot / make install-sync
```

В Docker устанавливается как зависимость через named build context
(`build.additional_contexts: { database: ./packages/db }` в `docker-compose.yaml`):

```dockerfile
COPY --from=database . /tmp/best_db
RUN pip3 install --no-cache-dir /tmp/best_db
```

## Использование

```python
from best_db.models import Person, LbgMember          # таблицы — отсюда
# engine/session — у каждого сервиса свой (из его env), напр. bot/database/main.py
```

## Миграции

URL собирается из окружения `POSTGRES_*` (`POSTGRES_HOST/PORT/USER/PASSWORD/DB`,
см. `best_db/migrations/env.py`). Запуск:

```bash
# локально (нужны переменные окружения; для dev-стека POSTGRES_HOST=localhost)
cd packages/db && alembic upgrade head            # или: make migrate
cd packages/db && alembic revision --autogenerate -m "..."   # make revision m="..."

# в сети docker-compose (host=postgres)
docker compose run --rm db_migrate                # или: make migrate-docker
```

Файлы в `best_db/migrations/versions/` **коммитятся** — это история схемы.
