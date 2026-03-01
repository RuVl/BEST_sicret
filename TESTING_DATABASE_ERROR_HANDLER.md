# Руководство по тестированию обработки ошибок БД

## Быстрый старт

### 1. Unit-тесты
```bash
# Установка зависимостей для тестирования
pip install pytest pytest-asyncio pytest-mock

# Запуск unit-тестов
pytest bot/tests/test_error_handler.py -v

# Запуск с подробным выводом
pytest bot/tests/test_error_handler.py -vv --tb=long
```

### 2. Интеграционные тесты
```bash
# Запуск интеграционного теста
python bot/tests/test_error_handler_integration.py
```

---

## Детальное описание тестов

### Unit-тесты (test_error_handler.py)

Проверяют все типы ошибок БД с mock-объектами:

#### 1. test_handle_db_commit_success
- **Что проверяет**: Успешный commit без ошибок
- **Ожидаемый результат**: `(True, None)`
- **Происходит**: Один вызов `session.commit()`

#### 2. test_handle_db_commit_integrity_error_duplicate
- **Что проверяет**: Обработка дублирования записей (UNIQUE constraint)
- **Симулирует**: IntegrityError с сообщением о duplicate key
- **Ожидаемый результат**: `(False, "❌ Такая запись уже существует")`
- **Происходит**: Вызов `session.rollback()`

#### 3. test_handle_db_commit_integrity_error_foreign_key
- **Что проверяет**: Нарушение внешних ключей (foreign key constraint)
- **Симулирует**: IntegrityError с сообщением о foreign key
- **Ожидаемый результат**: Ошибка с упоминанием "связи данных"
- **Происходит**: Вызов `session.rollback()`

#### 4. test_handle_db_commit_operational_error
- **Что проверяет**: Проблемы с подключением к БД
- **Симулирует**: OperationalError (connection refused)
- **Ожидаемый результат**: `(False, "❌ Ошибка подключения к БД")`
- **Происходит**: Вызов `session.rollback()`

#### 5. test_handle_db_commit_data_error
- **Что проверяет**: Неверный тип данных
- **Симулирует**: DataError (invalid data type)
- **Ожидаемый результат**: `(False, "❌ Ошибка данных")`
- **Происходит**: Вызов `session.rollback()`

#### 6. test_handle_db_commit_unexpected_error
- **Что проверяет**: Обработка непредвиденных ошибок
- **Симулирует**: RuntimeError
- **Ожидаемый результат**: `(False, error_message)`
- **Происходит**: Вызов `session.rollback()`

### Интеграционные тесты (test_error_handler_integration.py)

Используют реальную БД SQLite в памяти:

#### 1. TEST 1: Обработка дублирования записи
```
Шаги:
1. Создаем пользователя с username='john'
2. Пытаемся создать еще одного с же username
3. Проверяем что ошибка обработана корректно

Ожидается:
✅ Первый пользователь создан
❌ Второй commit упал (IntegrityError)
✅ Ошибка обработана с правильным сообщением
```

#### 2. TEST 2: Успешный commit
```
Шаги:
1. Создаем пользователя с уникальным username
2. Делаем commit

Ожидается:
✅ Commit прошел успешно
✅ Нет ошибок
```

#### 3. TEST 3: Откат транзакции
```
Шаги:
1. Создаем пользователя 'bob'
2. Пытаемся создать дубликат 'bob'
3. Проверяем что сессия очищена после rollback

Ожидается:
❌ Commit упал как ожидалось
✅ Сессия содержит 0 новых объектов (откат произошел)
```

---

## Ручное тестирование через бот

### Сценарий 1: Тестирование при создании пользователя

**Как вызвать IntegrityError:**

1. Запустите бота
2. Откройте две сессии с одинаковым Telegram ID
3. Оба отправят `/start` одновременно
4. Ожидаемо: вторая попытка создать пользователя упадет

**Проверяемое поведение:**
- ✅ Пользователь видит сообщение об ошибке
- ✅ В логах видна полная информация об ошибке
- ✅ Второй `/start` обработан корректно (no hanging transactions)

### Сценарий 2: Тестирование запроса на рефанд

**Как вызвать ошибку:**

1. Запустите команду `/request_refund`
2. Заполните форму
3. Во время подтверждения отключите БД:
   ```bash
   docker-compose down db  # Остановить PostgreSQL
   ```
4. Нажмите "Подтвердить"

**Проверяемое поведение:**
- ❌ User видит сообщение "Ошибка подключения к БД. Попробуйте позже"
- ✅ После восстановления БД бот продолжает работу
- ✅ В логах записана информация об ошибке

```bash
# Восстановить БД
docker-compose up -d db
```

### Сценарий 3: Тестирование базы имущества

**Как вызвать ошибку:**

1. Запустите команду `/property_database`
2. Заполните форму заявки
3. Отредактируйте таблицу БД чтобы удалить категорию:
   ```sql
   DELETE FROM categories WHERE id = 1;
   ```
4. Нажмите "Подтвердить"

**Проверяемое поведение:**
- ❌ User видит сообщение об ошибке связи данных
- ✅ Заявка не создана
- ✅ Пользователь может попробовать еще раз

---

## Чтение логов для проверки

При правильной работе error_handler в логах должны быть:

### При успешном commit:
```
INFO:database.error_handler:Successfully committed: create person
```

### При IntegrityError:
```
ERROR:database.error_handler:IntegrityError in create refund request (<handler>): ...
```

### При OperationalError:
```
ERROR:database.error_handler:OperationalError in create property application (<handler>): ...
```

### При откате:
```
ERROR:database.error_handler:DataError in insert data: ...
```

---

## Проверочный список

- [ ] Unit-тесты проходят: `pytest bot/tests/test_error_handler.py -v`
- [ ] Интеграционные тесты проходят: `python bot/tests/test_error_handler_integration.py`
- [ ] Логи содержат сообщения о коммитах
- [ ] При IntegrityError - корректный откат
- [ ] При OperationalError - корректное сообщение пользователю
- [ ] Нет "висящих" транзакций в логах
- [ ] Пользователь получает локализованные сообщения об ошибках
- [ ] После ошибки БД бот продолжает работать

---

## Запуск всех тестов разом

```bash
# Unit-тесты
pytest bot/tests/test_error_handler.py -v

# Интеграционные тесты
python bot/tests/test_error_handler_integration.py

# Оба разом (если установлен pytest)
pytest bot/tests/test_error_handler*.py -v
```

---

## Отладка при проблемах

Если тесты не проходят:

### 1. Проверьте импорты
```bash
python -c "from database.error_handler import handle_db_commit; print('✅ Import OK')"
```

### 2. Проверьте зависимости
```bash
pip list | grep -E "sqlalchemy|pytest|fluent"
```

### 3. Запустите с полным выводом ошибок
```bash
pytest bot/tests/test_error_handler.py -vv --tb=long --capture=no
python bot/tests/test_error_handler_integration.py 2>&1 | head -100
```

### 4. Проверьте версии библиотек
```bash
pip show sqlalchemy pytest
```

### 5. Очистите кэш Python
```bash
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

---

## Дополнительные проверки

### Проверка, что rollback вызывается
Добавьте временно в error_handler.py:
```python
async def handle_db_commit(...):
    try:
        await session.commit()
        print("✅ COMMIT OK")  # Видимо в логе
        return True, None
    except ... as e:
        print(f"⚠️  ROLLBACK CALLED")  # Видимо в логе
        await session.rollback()
        ...
```

### Проверка хендлеров
Проверьте что все три файла импортируют error_handler:
```bash
grep -n "from database.error_handler import" \
  bot/handlers/commands.py \
  bot/dialogs/user/request_refund.py \
  bot/dialogs/user/property_database.py
```

Должно быть 3 совпадения.

### Проверка локализации
Убедитесь что все ключи в main.ftl:
```bash
grep "^db-error-" bot/l10n/ru/main.ftl
```

Должно быть как минимум 5 ключей.
