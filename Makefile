# Единые команды разработки/деплоя.
#
# Кроссплатформенно (Linux / Windows): рецепты — это только `cd` + вызов бинарника
# (uv / docker compose). Файловые операции и парсинг делает Python через
# `uv run --no-project`, поэтому grep/sed/find/awk и POSIX-only трюки не нужны.
#
#   make init     — подготовить окружение с нуля
#   make run-bot  — бот локально (dev.env) + postgres/redis в docker
#   make run-sync — members_sync локально (dev.env) + postgres в docker
#   make up       — весь стек в docker (.env)
#   make help     — полный список целей
#
# Конфиги: `.env` — для запуска в docker/podman (хосты = имена сервисов compose),
# `dev.env` — оверрайды для локального запуска (POSTGRES_HOST=localhost и т.п.),
# грузятся поверх `.env` через `uv run --env-file dev.env`.

COMPOSE     ?= docker compose
COMPOSE_DEV ?= docker compose -f docker-compose.dev.yaml
UV          ?= uv
PY          ?= $(UV) run --no-project python
RUFF        ?= uvx ruff@0.15.12
PRECOMMIT   ?= uvx pre-commit

# Проекты для ruff (каждый со своим [tool.ruff]); корневые scratch-файлы не трогаем.
RUFF_PATHS  ?= bot members_sync packages/db

# Параметры БД для локальных команд (можно переопределить: make db-dump PG_USER=…)
PG_USER ?= user
PG_DB   ?= database
DUMP    ?= backups/dump.sql
rev     ?= -1

.DEFAULT_GOAL := help

.PHONY: help
help: ## Показать список целей
	@$(PY) -c "import re; [print(f'  {m[1]:<20} {m[2]}') for l in open('Makefile', encoding='utf-8') for m in [re.match(r'^([A-Za-z_-]+):.*?## (.*)', l)] if m]"

# --- Подготовка окружения ---------------------------------------------------

.PHONY: init
init: ## Подготовить окружение с нуля (deps → .env → venv → pre-commit → миграции)
	$(MAKE) check-deps
	$(MAKE) env
	$(MAKE) install
	$(MAKE) pre-commit-install
	$(MAKE) infra
	$(MAKE) migrate
	@echo "OK: окружение готово. Запуск бота: make run-bot"

.PHONY: check-deps
check-deps: ## Проверить наличие uv и docker compose
	$(UV) --version
	$(COMPOSE) version

.PHONY: env
env: ## Создать .env (docker) и dev.env (локальный запуск) из *.dist, где их нет
	@$(PY) -c "import os, shutil; [(shutil.copyfile(t+'.dist', t), print('created', t)) for t in ('bot/.env','members_sync/.env','postgres/.env','redis/.env','bot/dev.env','members_sync/dev.env') if os.path.isfile(t+'.dist') and not os.path.isfile(t)]"
	@echo "Заполните .env (docker/podman) и dev.env (локальный запуск)!"

# --- Установка зависимостей (все venv) -------------------------------------

.PHONY: install
install: install-db install-bot install-sync ## Поставить зависимости во все venv

.PHONY: install-db
install-db: ## venv общего пакета best_db (packages/db)
	cd packages/db && $(UV) sync

.PHONY: install-bot
install-bot: ## venv бота (+ best_db editable)
	cd bot && $(UV) sync

.PHONY: install-sync
install-sync: ## venv members_sync (+ best_db editable, + dev: pytest)
	cd members_sync && $(UV) sync

# --- Запуск -----------------------------------------------------------------

.PHONY: infra
infra: ## Поднять только postgres + redis в docker (порты на host)
	$(COMPOSE_DEV) up -d

.PHONY: infra-down
infra-down: ## Остановить локальную инфраструктуру
	$(COMPOSE_DEV) down

.PHONY: run-bot
run-bot: ## Бот локально (dev.env) + postgres/redis в docker
	$(COMPOSE_DEV) up -d
	cd bot && $(UV) run --env-file dev.env python run.py

.PHONY: run-sync
run-sync: ## members_sync локально (dev.env) + postgres в docker (RUN_MODE из .env)
	$(COMPOSE_DEV) up -d postgres
	cd members_sync && $(UV) run --env-file dev.env python run.py

.PHONY: run-sync-dry
run-sync-dry: ## members_sync: парсинг боевых данных в JSON без записи в БД (dry-run, postgres не нужен)
	cd members_sync && $(UV) run --env-file dev.env python run.py --dry-run

.PHONY: up
up: ## Поднять весь стек в docker (bot + members_sync + postgres + redis)
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Остановить стек
	$(COMPOSE) down

.PHONY: build
build: ## Пересобрать образы
	$(COMPOSE) build

.PHONY: ps
ps: ## Статус контейнеров
	$(COMPOSE) ps

# --- Миграции (единый alembic в packages/db) -------------------------------
# uv сам читает postgres/.env (--env-file), POSTGRES_HOST там не задан → localhost.

.PHONY: migration
migration: ## Новая ревизия: make migration m="описание"
	cd packages/db && $(UV) run --env-file ../../postgres/.env alembic revision --autogenerate -m "$(m)"

.PHONY: migrate
migrate: ## Применить миграции к локальной бд
	cd packages/db && $(UV) run --env-file ../../postgres/.env alembic upgrade head

.PHONY: downgrade
downgrade: ## Откатить миграции: make downgrade [rev=-1]
	cd packages/db && $(UV) run --env-file ../../postgres/.env alembic downgrade $(rev)

.PHONY: migrate-docker
migrate-docker: ## Применить миграции бд в докере
	$(COMPOSE) run --rm db_migrate

# --- Логи -------------------------------------------------------------------

.PHONY: logs
logs: ## Логи всего стека (follow)
	$(COMPOSE) logs -f

.PHONY: logs-bot
logs-bot: ## Логи бота
	$(COMPOSE) logs -f telegram_bot

.PHONY: logs-db
logs-db: ## Логи postgres
	$(COMPOSE) logs -f postgres

.PHONY: logs-redis
logs-redis: ## Логи redis
	$(COMPOSE) logs -f redis

# --- База данных: дамп / импорт --------------------------------------------
# Подключение внутри контейнера по unix-сокету (trust-auth, пароль не нужен).

.PHONY: db-dump
db-dump: ## Дамп БД в файл (по умолчанию backups/dump.sql; DUMP=… для другого)
	$(MAKE) infra
	$(COMPOSE) exec -T postgres pg_dump -U $(PG_USER) -d $(PG_DB) > $(DUMP)
	@echo "dumped -> $(DUMP)"

.PHONY: db-restore
db-restore: ## Восстановить БД из файла: make db-restore DUMP=backups/x.sql
	$(MAKE) infra
	$(COMPOSE) exec -T postgres psql -U $(PG_USER) -d $(PG_DB) < $(DUMP)
	@echo "restored <- $(DUMP)"

.PHONY: psql
psql: ## Интерактивный psql в контейнере
	$(MAKE) infra
	$(COMPOSE) exec postgres psql -U $(PG_USER) -d $(PG_DB)

# --- Redis ------------------------------------------------------------------

.PHONY: redis-flush
redis-flush: ## Очистить весь кэш redis (FLUSHALL)
	$(COMPOSE) exec redis redis-cli FLUSHALL

# --- Качество кода ----------------------------------------------------------

.PHONY: pre-commit-install
pre-commit-install: ## Установить git-хуки pre-commit
	$(PRECOMMIT) install

.PHONY: pre-commit
pre-commit: ## Прогнать pre-commit по всем файлам
	$(PRECOMMIT) run --all-files

.PHONY: lint
lint: ## ruff check + проверка форматирования (без правок)
	$(RUFF) check $(RUFF_PATHS)
	$(RUFF) format --check $(RUFF_PATHS)

.PHONY: format
format: ## ruff format + автофиксы
	$(RUFF) check --fix $(RUFF_PATHS)
	$(RUFF) format $(RUFF_PATHS)

.PHONY: test
test: ## Юнит-тесты members_sync
	cd members_sync && $(UV) run pytest

# --- Очистка ----------------------------------------------------------------

.PHONY: clean
clean: ## Удалить кэши (pycache, ruff, mypy, pytest)
	@$(PY) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for n in ('__pycache__','.ruff_cache','.mypy_cache','.pytest_cache') for p in pathlib.Path('.').rglob(n)]"
	@echo "OK: кэши очищены"

.PHONY: clean-venv
clean-venv: ## Удалить все venv (.venv каждого сервиса)
	@$(PY) -c "import shutil; [shutil.rmtree(d, ignore_errors=True) for d in ('bot/.venv','members_sync/.venv','packages/db/.venv')]"
	@echo "OK: venv удалены (восстановить: make install)"

.PHONY: nuke
nuke: ## Остановить стек и СТЕРЕТЬ данные (postgres/redis тома)
	$(COMPOSE) down -v
	$(COMPOSE_DEV) down -v
