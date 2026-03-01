# ПРОБЛЕМА 6: Обработка ошибок БД — дублирование логики

## Описание проблемы

В исходной реализации:
- Обработка ошибок БД предполагалась на уровне каждого handler'а
- Это приводило бы к дублированию кода try/except блоков
- Отсутствовала централизованная логика обработки разных типов ошибок БД
- Не было единого подхода к логированию и уведомлению пользователей об ошибках

## Решение

### 1. Централизованный модуль обработки ошибок

Создан модуль `bot/database/error_handler.py` с тремя инструментами:

#### 1.1. Функция `handle_db_commit()`
```python
async def handle_db_commit(
    session: AsyncSession,
    l10n: FluentLocalization,
    operation_name: str = "database operation"
) -> tuple[bool, Optional[str]]
```

**Назначение**: Безопасный commit с централизованной обработкой ошибок БД.

**Возвращает**:
- `(True, None)` - если commit успешен
- `(False, error_message)` - если произошла ошибка

**Обрабатывает**:
- `IntegrityError` - нарушения целостности (unique, foreign key)
- `OperationalError` - проблемы подключения к БД
- `DataError` - неверные данные
- `SQLAlchemyError` - прочие ошибки SQLAlchemy
- `Exception` - неожиданные ошибки

**Автоматически**:
- Делает `rollback` при ошибке
- Логирует ошибку с контекстом операции
- Возвращает локализованное сообщение для пользователя

#### 1.2. Декоратор `@handle_db_errors`
```python
@handle_db_errors(operation_name="create refund")
async def on_confirm_application(clb: CallbackQuery, ...):
    ...
```

**Назначение**: Автоматическая обработка ошибок БД в handler функциях.

**Требования**:
- В kwargs должен быть `dialog_manager`
- В `middleware_data` должны быть `session` и `l10n_format`

**Автоматически**:
- Перехватывает исключения БД
- Выполняет rollback
- Отправляет пользователю alert с описанием ошибки
- Логирует ошибку

#### 1.3. Функция `safe_commit()`
```python
async def safe_commit(
    session: AsyncSession,
    operation_name: str = "database operation"
) -> None
```

**Назначение**: Простой commit с логированием для случаев, где обработка на верхнем уровне.

### 2. Внедрение в код

#### 2.1. handlers/commands.py
```python
from database.error_handler import handle_db_commit

@router.message(CommandStart())
async def start(msg: Message, l10n: FluentLocalization):
    async with async_session() as session:
        person = await get_person_by_telegram_id(session, msg.from_user.id)
        if person is None:
            person = await create_person(...)
            # ✅ Централизованная обработка
            success, error_msg = await handle_db_commit(session, l10n, "create person")
            if not success:
                await msg.answer(error_msg)
                return
        ...
```

#### 2.2. dialogs/user/request_refund.py
```python
from database.error_handler import handle_db_commit

async def on_confirm_application(clb: CallbackQuery, ...):
    ...
    refund_request = await create_refund(...)
    
    # ✅ Централизованная обработка
    success, error_msg = await handle_db_commit(session, l10n, "create refund request")
    if not success:
        await clb.answer(error_msg, show_alert=True)
        return
    
    # Продолжаем только при успешном commit
    await clb.bot.send_message(...)
```

#### 2.3. dialogs/user/property_database.py
```python
from database.error_handler import handle_db_commit

async def on_confirm_application(clb: CallbackQuery, ...):
    ...
    application = await create_application(...)
    
    # ✅ Централизованная обработка
    success, error_msg = await handle_db_commit(session, l10n, "create property application")
    if not success:
        await clb.answer(error_msg, show_alert=True)
        return
    
    await clb.bot.send_message(...)
```

### 3. Локализация ошибок

Добавлены ключи в `bot/l10n/ru/main.ftl`:

```ftl
# Database errors
db-error-duplicate-entry = ❌ Ошибка: такая запись уже существует в базе данных
db-error-connection = ❌ Ошибка подключения к базе данных. Попробуйте позже
db-error-data = ❌ Ошибка данных: проверьте корректность введенной информации
db-error-unknown = ❌ Произошла непредвиденная ошибка базы данных
db-error-foreign-key = ❌ Ошибка связи данных при операции: { $operation }
user-not-found = ❌ Пользователь не найден в системе
```

## Преимущества решения

### 1. Отсутствие дублирования кода
- Вся логика обработки ошибок в одном месте
- Единый подход к обработке разных типов ошибок
- Легко изменить поведение для всего приложения

### 2. Улучшенное логирование
- Унифицированный формат логов
- Контекст операции в каждом логе
- Разные уровни логирования для разных ошибок

### 3. Лучший UX
- Локализованные сообщения для пользователя
- Понятные описания ошибок
- Автоматический rollback при ошибках

### 4. Безопасность транзакций
- Гарантированный rollback при любой ошибке
- Нет "висящих" транзакций
- Предсказуемое поведение БД

### 5. Расширяемость
- Легко добавить обработку новых типов ошибок
- Можно добавить метрики/мониторинг в одном месте
- Простая интеграция с системами оповещений

## Паттерн использования

### Рекомендуемый подход
Используйте `handle_db_commit()` для явного контроля:

```python
result = await create_something(session, ...)
success, error_msg = await handle_db_commit(session, l10n, "operation name")
if not success:
    await callback.answer(error_msg, show_alert=True)
    return
# Продолжаем только при успехе
```

### Альтернатива с декоратором
Для простых handler'ов можно использовать декоратор:

```python
@handle_db_errors(operation_name="operation name")
async def handler(clb: CallbackQuery, dialog_manager: DialogManager):
    session = dialog_manager.middleware_data['session']
    await create_something(session, ...)
    await session.commit()  # Будет обработано декоратором
```

## Тестирование

Для тестирования обработки ошибок:

1. **IntegrityError**: Попробуйте создать дубликат записи
2. **OperationalError**: Остановите БД во время операции
3. **DataError**: Передайте данные неверного типа
4. **ConnectionError**: Отключите сеть к БД

Ожидаемое поведение:
- Пользователь видит понятное сообщение
- В логах видна полная информация об ошибке
- Транзакция откатилась
- Приложение продолжает работу

## Статус: ✅ РЕШЕНО

Дата решения: 1 марта 2026

### Изменённые файлы:
1. ✅ **Создан**: `bot/database/error_handler.py` - централизованный модуль
2. ✅ **Изменён**: `bot/handlers/commands.py` - внедрена обработка в `/start`
3. ✅ **Изменён**: `bot/dialogs/user/request_refund.py` - обработка при создании рефанда
4. ✅ **Изменён**: `bot/dialogs/user/property_database.py` - обработка при создании заявки
5. ✅ **Изменён**: `bot/l10n/ru/main.ftl` - добавлены ключи локализации ошибок

### Результат:
- ❌ **Было**: Дублирование try/except блоков в каждом handler'е
- ✅ **Стало**: Централизованная обработка ошибок БД без дублирования кода
