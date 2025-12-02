# Быстрый старт

## 1. Настройка переменных окружения

Создайте файл `bot/.env` со следующими переменными:

```env
# Telegram Bot API
TG_API_TOKEN=your_bot_token_here
PRESIDENT_ID=0  # ID президента для уведомлений (опционально)
TREASURER_ID=0  # ID казначея для уведомлений (опционально)

# PostgreSQL Database
DOCKER_POSTGRES_HOST=localhost
DOCKER_POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=database

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Project settings
DEBUG=false
TEMPLATES_DIR=resources/templates/
LOCALE_DIR=l10n/
AVAILABLE_LOCALES=ru

# Logging
SHOW_DEBUG_LOGS=false
LOG_TO_FILE=true
LOG_FILE_PATH=logs/bot.log
```

## 2. Установка зависимостей

Убедитесь, что у вас установлен Python 3.12+, затем установите зависимости:

```bash
cd bot
pip install -r requirements.txt
```

## 3. Настройка базы данных

### Вариант А: Использование Docker Compose (рекомендуется)

1. Создайте файлы конфигурации для сервисов:

**postgres/.env:**
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=database
```

**redis/.env:**
```env
# Обычно пустой файл или с настройками Redis при необходимости
```

2. Запустите PostgreSQL и Redis через Docker Compose:
```bash
docker-compose up -d postgres redis
```

### Вариант Б: Установка локально

- Установите PostgreSQL 17.6+ и Redis 8.2.2+
- Создайте базу данных PostgreSQL
- Убедитесь, что Redis запущен

## 4. Применение миграций базы данных

```bash
cd bot
alembic upgrade head
```

Если миграций еще нет, создайте их:
```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## 5. Запуск бота

### Локальный запуск

```bash
cd bot
python run.py
```

### Запуск через Docker Compose

```bash
docker-compose up telegram_bot
```

## Проверка работы

После запуска бот должен:
1. Подключиться к базе данных
2. Подключиться к Redis
3. Начать получать обновления от Telegram

Откройте Telegram и найдите вашего бота, затем отправьте команду `/start`.

## Доступные команды

- `/start` - Запуск бота
- `/create_document` - Создать приказ
- `/property_database` - База имущества
- `/request_refund` - Запросить рефанд

## Решение проблем

### Ошибка подключения к БД
- Проверьте, что PostgreSQL запущен и доступен
- Проверьте правильность данных в `.env` файле
- Убедитесь, что база данных создана

### Ошибка подключения к Redis
- Проверьте, что Redis запущен
- Проверьте порт и хост в `.env` файле

### Ошибка миграций
- Убедитесь, что база данных существует
- Проверьте права доступа к БД
- Убедитесь, что все модели импортированы в `database/models/__init__.py`

## Остановка бота

Для остановки нажмите `Ctrl+C` в терминале.

Если использовали Docker Compose:
```bash
docker-compose down
```

