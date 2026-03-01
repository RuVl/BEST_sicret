# Быстрый старт: Тестирование обработки ошибок БД

## ⚡ 30-секундный тест

```bash
# 1. Перейдите в папку проекта
cd d:\BEST_sicret-dev_troubleshooting

# 2. Запустите интеграционный тест (самый быстрый)
python bot/tests/test_error_handler_integration.py
```

**Ожидаемый результат:**
```
==================================================
TEST 1: Обработка дублирования записи
==================================================
✅ Первый пользователь создан
❌ Commit упал как ожидалось
✅ Ошибка обработана корректно

...

==================================================
✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО
==================================================
```

---

## 📋 Полный набор тестов

### 1️⃣ Unit-тесты (5мин)
```bash
pip install pytest pytest-asyncio pytest-mock
pytest bot/tests/test_error_handler.py -v
```

**Проверяет:**
- ✅ Успешный commit
- ❌ IntegrityError (duplicate, foreign key)
- ❌ OperationalError (connection)
- ❌ DataError (invalid data)
- ❌ Непредвиденные ошибки

---

### 2️⃣ Интеграционные тесты (1мин)
```bash
python bot/tests/test_error_handler_integration.py
```

**Проверяет:**
- ✅ Успешный commit с реальной БД SQLite
- ❌ Обработка дублирования с реальной constraint
- ❌ Откат после ошибки

---

### 3️⃣ Ручные тесты через JSON API (2мин)

```bash
# Запустите бота если еще не запущен
docker-compose up -d

# Тест 1: Дублирование при /start
python -c """
import asyncio
from aiogram import types
from bot.handlers.commands import start

# Симулируем два /start с одинаковым telegram_id
# (в реальности нужна полная setup)
"""

# Тест 2: Через интерактивное меню
# Откройте Telegram и отправьте /start
# Затем /request_refund и заполните форму
```

---

### 4️⃣ Тестирование потери соединения (3мин)

```bash
# Терминал 1: Следите за логами
docker logs -f best_sicret_bot

# Терминал 2: Запустите команду в Telegram
/request_refund
# Заполните форму

# Терминал 3: Отключите БД
docker-compose down db

# В Telegram нажмите "Подтвердить"
# Ожидается: "❌ Ошибка подключения к БД"

# Восстановите БД
docker-compose up -d db

# Попробуйте еще раз - должно работать
```

---

## 📊 Матрица тестирования

| Сценарий | Unit | Интеграция | Вручную (ТГ) | Время |
|----------|------|-----------|------------|-------|
| ✅ Успешный commit | ✅ | ✅ | ✅ | 1мин |
| ❌ Дублирование (UNIQUE) | ✅ | ✅ | ✅ | 2мин |
| ❌ Foreign key | ✅ | - | - | 1мин |
| ❌ Потеря соединения | ✅ | - | ✅ | 3мин |
| ❌ Неверные данные | ✅ | - | - | 1мин |
| ↩️ Откат транзакции | ✅ | ✅ | ✅ | 1мин |

**Рекомендуем запустить:**
1. **Быструю проверку (3мин)**: запустите `test_error_handler_integration.py`
2. **Полную проверку (15мин)**: запустите все unit и integration тесты
3. **Финальную проверку (5мин)**: тестируйте передачи соединения через бот

---

## 🎯 Что проверяет каждый тест

### test_error_handler.py (Unit-тесты)

```
test_handle_db_commit_success()
└─ Проверяет: успешный commit возвращает (True, None)

test_handle_db_commit_integrity_error_duplicate()
└─ Проверяет: дублирование возвращает (False, error_msg)
  └─ error_msg содержит "существует" или "duplicate"

test_handle_db_commit_integrity_error_foreign_key()
└─ Проверяет: нарушение FK возвращает (False, error_msg)
  └─ error_msg содержит "связи" или "foreign"

test_handle_db_commit_operational_error()
└─ Проверяет: потеря соединения возвращает (False, error_msg)
  └─ error_msg содержит "подключения" или "connection"

test_handle_db_commit_data_error()
└─ Проверяет: неверные данные возвращают (False, error_msg)
  └─ error_msg содержит "данных" или "data"

test_handle_db_commit_unexpected_error()
└─ Проверяет: неожиданные ошибки обработаны
  └─ Возвращает (False, error_msg) с генерическим сообщением
```

### test_error_handler_integration.py (Интеграционные)

```
TEST 1: Обработка дублирования записи
├─ Создает пользователя 'john'
├─ Пытается создать второго 'john'
├─ Проверяет: ошибка обработана, rollback вызван
└─ Ожидается: ❌ FAILED, но с правильным сообщением

TEST 2: Успешный commit
├─ Создает пользователя 'alice'
├─ Проверяет: commit прошел успешно
└─ Ожидается: ✅ SUCCESS

TEST 3: Откат транзакции
├─ Создает пользователя 'bob'
├─ Пытается создать дубликат
├─ Проверяет: сессия очищена (0 новых объектов)
└─ Ожидается: после rollback нет "висящих" данных
```

---

## 🔍 Как читать результаты

### ✅ Успех
```
TEST 2: Успешный commit
========================================
Результат: ✅ SUCCESS
Commit прошел успешно
```

### ❌ Правильная ошибка
```
TEST 1: Обработка дублирования записи
========================================
Результат: ❌ COMMIT FAILED
Сообщение ошибки: ❌ Ошибка: такая запись уже существует
✅ Ошибка обработана корректно
```

### ⚠️ Проблема
```
Результат: ✅ SUCCESS
❌ ОШИБКА: commit не должен был пройти!
```
(Это значит что constraint не работает или ошибка не была перехвачена)

---

## 🐛 Если тесты не проходят

### 1. Импорт не работает
```bash
# Проверьте что файл существует
ls bot/database/error_handler.py
# Должен быть: error_handler.py

# Проверьте что модуль импортируется
python -c "from database.error_handler import handle_db_commit; print('OK')"
```

### 2. Зависимости не установлены
```bash
# Проверьте установку зависимостей
pip list | grep -E "sqlalchemy|pytest"

# Установите если не хватает
pip install pytest pytest-asyncio sqlalchemy aiosqlite
```

### 3. БД не работает (для интеграционных тестов)
```bash
# Проверьте что контейнеры запущены
docker-compose ps

# Запустите если нужно
docker-compose up -d db redis
```

### 4. Синтаксические ошибки
```bash
# Проверьте синтаксис Python файлов
python -m py_compile bot/database/error_handler.py
python -m py_compile bot/tests/test_error_handler.py

# Если есть ошибки - исправьте их
```

---

## 📝 Создание CI/CD пайплайна

Если планируете автоматизировать тесты:

```yaml
# .github/workflows/test_error_handler.yml
name: Test Error Handler

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r bot/requirements.txt
          pip install pytest pytest-asyncio pytest-mock
      
      - name: Run unit tests
        run: pytest bot/tests/test_error_handler.py -v
      
      - name: Run integration tests
        run: python bot/tests/test_error_handler_integration.py
```

---

## ✅ Проверочный лист

Перед сдачей:

- [ ] `python bot/tests/test_error_handler_integration.py` прошел успешно
- [ ] `pytest bot/tests/test_error_handler.py -v` показал все passed
- [ ] В логах видны сообщения об успешных commits
- [ ] При отключении БД видно сообщение об ошибке
- [ ] После восстановления БД бот продолжает работу
- [ ] Пользователь видит локализованные сообщения об ошибках
- [ ] В коде нет дублирования try/except блоков

Если все галочки ✅ - решение готово к использованию!
