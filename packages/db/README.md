# best_db - общая схема БД

Единственный владелец таблиц Postgres для `bot` и `members_sync`: все модели SQLAlchemy (`best_db.models`) и единая
история alembic (`best_db/migrations`). Сервисы импортируют модели отсюда, но держат свой engine и sessionmaker. Общий
`Base` нужен, чтобы работали связи между моделями разных сервисов, например `Person.lbg_member`.

```python
from best_db.models import LbgMember, Person
```

В venv сервисов пакет ставится editable (`make install-bot`, `make install-sync`), в Docker приезжает через
`additional_contexts` в `docker-compose.yaml`.

## Миграции

```bash
make migration m="..."   # новая ревизия по изменениям моделей: прочитайте файл перед применением
make migrate             # применить локально
make migrate-docker      # применить в сети docker-compose
make downgrade rev=-1    # откатить
```

URL собирается из `POSTGRES_HOST/PORT/USER/PASSWORD/DB`, для локального стека `POSTGRES_HOST=localhost`. Файлы в
`best_db/migrations/versions/` коммитятся: это история схемы.
