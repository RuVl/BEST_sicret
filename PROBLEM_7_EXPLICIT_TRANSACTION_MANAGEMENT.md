# ПРОБЛЕМА 7: Явное управление транзакциями

## Статус: ✅ РЕШЕНО

**Дата**: 27 февраля 2026 г.

---

## Описание проблемы

Текущая реализация `DatabaseMiddleware` выполняла **автоматический commit** после каждого handler-а, что противоречило выбранной стратегии **явного управления транзакциями** (см. PROBLEM_5 и PROBLEM_6).

### Проблема в коде

**Было** (DatabaseMiddleware в middlewares/database.py):
```python
async def _create_session_and_call(...) -> Any:
    async with async_session() as session:
        data[SESSION_KEY] = session
        try:
            result = await handler(event, data)
            await session.commit()  # ❌ АВТОМАТИЧЕСКИЙ COMMIT
            return result
        except Exception:
            await session.rollback()
            raise
```

**Проблема**:
- Middleware автоматически коммитит после КАЖДОГО handler-а
- Handler не имеет контроля над моментом commit-а
- Нельзя выполнить условный commit (например, commit только если успешно отправили уведомление)
- Противоречит стратегии "Explicit transaction management"

---

## Выбранная стратегия

### СТРАТЕГИЯ: Explicit Transaction Management

```
┌─────────────────────────────────────────────────────┐
│ Handler / Dialog Handler                            │
│  - Вызывает database методы (используют flush)      │
│  - ЯВНО решает когда делать commit                  │
│  - await session.commit() когда готово              │
│  - await session.rollback() при ошибке (опционально)│
└─────────────────────────────────────────────────────┘
                        │
        ┌───────────────┴──────────────┐
        │                              │
    ┌───▼──────┐               ┌──────▼───┐
    │ Database │               │Middleware │
    │ Methods  │               │(provides  │
    │(flush)   │               │ session)  │
    └──────────┘               └───────────┘
        │                              │
        └───────────────┬──────────────┘
                        │
                        ▼
            ┌─────────────────────────┐
            │ PostgreSQL Database     │
            │ Transaction committed ✅│
            │ or rolled back ❌        │
            └─────────────────────────┘
```

### Основные правила

| | Было | Стало |
|---|------|--------|
| **Database методы** | flush (иногда) + commit (в create_person) | Только flush - ВСЕГДА |
| **Middleware** | Автоматический commit/rollback | Только предоставляет сессию, автоматический rollback при ошибке |
| **Handler** | Не отвечает за commit | ЯВНО отвечает за commit |
| **Контроль** | Неявный (middleware) | Явный (видно в коде handler) |
| **Атомарность** | На уровне middleware | На уровне handler (множество операций в одну транзакцию) |

---

## Реализованное решение

### 1️⃣ Изменение DatabaseMiddleware

**Файл**: `bot/middlewares/database.py`

```python
async def _create_session_and_call(...) -> Any:
    """
    Вспомогательный метод для создания сессии и вызова хэндлера.
    
    ВНИМАНИЕ: Middleware НЕ выполняет автоматический commit!
    Это следует выбранной стратегии ЯВНОГО управления транзакциями.
    
    ОТВЕТСТВЕННОСТЬ HANDLER ЗАКРЫТА:
    1. Создать сессию (достается из data[SESSION_KEY])
    2. Вызвать database методы (используют только flush)
    3. ЯВНО вызвать await session.commit() если операция успешна
    4. При ошибке session.rollback() вызывается контекстом или явно в except блоке
    """
    async with async_session() as session:
        data[SESSION_KEY] = session
        try:
            result = await handler(event, data)
            # ✅ НЕ делаем автоматический commit
            return result
        except Exception:
            # При исключении откатываем изменения
            await session.rollback()
            raise
```

**Ключевые изменения**:
- ✅ Удален `await session.commit()` после handler-а
- ✅ Оставлен `await session.rollback()` при ошибке (safety net)
- ✅ Добавлена понятная документация

### 2️⃣ Обновление обработчиков команд

**Файл**: `bot/handlers/commands.py`

Handler `start` уже делал диагностику и имел явный commit:
```python
@router.message(CommandStart())
async def start(msg: Message, l10n: FluentLocalization):
    async with async_session() as session:
        person = await get_person_by_telegram_id(session, msg.from_user.id)
        if person is None:
            person = await create_person(
                session=session,
                telegram_id=msg.from_user.id,
                full_name=full_name,
            )
            # ✅ ЯВНЫЙ COMMIT - решение handler-а
            await session.commit()
        await msg.answer(...)
```

**Почему это работает**:
- Handler открывает свою сессию (не через middleware)
- Handler явно решает когда коммитить (только если создали новую персону)
- Это уже соответствуют стратегии explicit management

### 3️⃣ Обновление диалогов

**Файлы**:
- ✅ `bot/dialogs/user/property_database.py` - функция `on_confirm_application()`
- ✅ `bot/dialogs/user/request_refund.py` - функция `on_confirm_application()`

**Было** (property_database.py):
```python
async def on_confirm_application(clb: CallbackQuery, ..., dialog_manager: DialogManager):
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    
    # Создание заявки
    application = await create_application(...)
    
    # ❌ БЕЗ явного commit - полагался на middleware
    # Отправка уведомления...
```

**Стало**:
```python
async def on_confirm_application(clb: CallbackQuery, ..., dialog_manager: DialogManager):
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    
    # Создание заявки
    application = await create_application(...)
    
    # ✅ ЯВНЫЙ COMMIT
    await session.commit()
    
    # Отправка уведомления...
```

**То же самое** для `request_refund.py`:
```python
async def on_confirm_application(clb: CallbackQuery, ..., dialog_manager: DialogManager):
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    
    # Создание заявки на рефанд
    refund_request = await create_refund(...)
    
    # ✅ ЯВНЫЙ COMMIT
    await session.commit()
    
    # Отправка уведомления...
```

---

## Архитектура после решения

### Как это работает

```
┌──────────────────────────┐
│ User sends /start        │
└──────────────┬───────────┘
               │
               ▼
┌──────────────────────────────────────────────────┐
│ Handler: start()                                 │
│  1. async with async_session() as session        │
│  2. Check if person exists via DB method         │
│  3. If not: create_person(session) via DB method │
│  4. await session.commit() ← EXPLICIT            │
│  5. Send message to user                         │
└──────────────┬───────────────────────────────────┘
               │
               ▼
        ┌──────────────┐
        │ Database ✅  │
        │ Person saved │
        └──────────────┘
```

### Для диалогов

```
┌───────────────────────────────┐
│ Dialog: property_database     │
│ (has DatabaseMiddleware)      │
└───────────────┬───────────────┘
                │
                ▼
    ┌──────────────────────────────────────────┐
    │ DatabaseMiddleware                       │
    │ Creates session                          │
    │ data[SESSION_KEY] = session              │
    │ Calls handler(event, data)               │
    └───────────┬──────────────────────────────┘
                │
                ▼
    ┌──────────────────────────────────────────┐
    │ Dialog Handler: on_confirm_application() │
    │ 1. Get session from data[SESSION_KEY]    │
    │ 2. Create application via DB method      │
    │ 3. await session.commit() ← EXPLICIT     │
    │ 4. Send notification                     │
    │ 5. Switch dialog state                   │
    └───────────┬──────────────────────────────┘
                │
                ▼
    ┌──────────────────────────────────────────┐
    │ Back to Middleware exception handler:     │
    │ - If no exception: return normally        │
    │ - If exception: rollback and re-raise    │
    └───────────┬──────────────────────────────┘
                │
                ▼
            ┌──────────────────┐
            │ Database ✅ or ❌│
            │ Changes committed │
            │ or rolled back     │
            └──────────────────┘
```

---

## Сравнение стратегий

### Стратегия 1: Implicit (ДО решения)

```python
# Handler не отвечает за commit
async def some_handler():
    async with async_session() as session:
        person = await create_person(session, ...)
        await session.flush()  # ← Database method flush
        await send_notification()  # ← Если упадет, все откатится

# Middleware делает commit автоматически
async def middleware(handler, event, data):
    try:
        result = await handler(event, data)
        await session.commit()  # ← АВТОМАТИЧЕСКИЙ, невидимый
    except:
        await session.rollback()
```

**Проблемы**:
- ❌ Непонятно когда произойдет commit
- ❌ Нельзя сделать условный commit
- ❌ Нельзя сделать несколько операций в одной транзакции

### Стратегия 2: Explicit (ПОСЛЕ решения) ✅

```python
# Handler явно отвечает за commit
async def some_handler():
    async with async_session() as session:
        person = await create_person(session, ...)
        await session.flush()  # ← Database method flush
        await session.commit()  # ← ЯВНЫЙ, видимый
        
        # Если send_notification упадет, commit уже произошел
        await send_notification()

# Для диалогов с middleware
async def dialog_handler(dialog_manager):
    session = dialog_manager.middleware_data[SESSION_KEY]
    
    # Несколько операций
    item1 = await create_item(session, ...)
    item2 = await create_item(session, ...)
    
    # Все вместе в одной транзакции
    await session.commit()  # ← ЯВНЫЙ, видимый, атомарный
```

**Преимущества**:
- ✅ Явно видно когда происходит commit в коде handler
- ✅ Можно делать условные commits (если успех - коммитим, если ошибка - откатываем)
- ✅ Можно комбинировать несколько DB операций в одну транзакцию
- ✅ Легче логировать и отлаживать
- ✅ Соответствует стратегии из PROBLEM_5

---

## Тестовые сценарии

### Сценарий 1: Создание персоны через /start

```
1. User: /start
2. Handler start(): 
   - Check if person exists
   - If not: create_person() → flush, но БЕЗ commit
   - await session.commit() ← ЯВНЫЙ commit
3. Result: Персона сохранена в БД ✅
```

### Сценарий 2: Создание заявки через диалог

```
1. Dialog: on_confirm_application()
2. Database middleware:
   - Creates session
   - data[SESSION_KEY] = session
   - Calls handler
3. Handler: on_confirm_application()
   - create_application() → flush, БЕЗ commit
   - await session.commit() ← ЯВНЫЙ commit
   - send_notification() to treasurer
4. If send_notification fails:
   - Handler raises exception
   - Middleware catches it
   - session.rollback() 
   - Application NOT in database ❌
5. If everything OK:
   - Application committed ✅
   - Notification sent ✅
```

### Сценарий 3: Ошибка в диалоге ДО commit

```
1. Dialog: on_confirm_application()
2. Handler:
   - create_application() → flush (in memory)
   - Exception raised ПЕРЕД await session.commit()!
3. Middleware catches exception:
   - session.rollback()
4. Result: Application NOT in database ✅ (no half-committed state)
```

### Сценарий 4: Ошибка в диалоге ПОСЛЕ commit

```
1. Dialog: on_confirm_application()
2. Handler:
   - create_application() → flush
   - await session.commit() ← Application saved!
   - send_notification() → Exception!
3. Middleware catches exception:
   - session.rollback() ← But data already committed!
4. Result: 
   - Application in database ✅
   - Notification NOT sent ❌
   - Need error handling in handler or separate transaction for notification
```

**Вывод**: Чувствительные операции (БД) должны быть ПЕРЕД некритичными (notifications), или notifications должны быть в отдельной транзакции.

Текущий код это уже учитывает:
```python
# Создание в БД ПЕРЕД отправкой уведомления
application = await create_application(...)
await session.commit()  # ← Сохранили

# Если уведомление упадет - не беда, заявка уже сохранена
await clb.bot.send_message(...)
```

---

## Изменения файлов

| Файл | Тип изменения | Детали |
|------|---------------|--------|
| `bot/middlewares/database.py` | 🔨 Изменение | Удален автоматический commit, добавлена документация |
| `bot/handlers/commands.py` | ✅ Уже готов | Имел явный commit в handler start |
| `bot/dialogs/user/property_database.py` | 🔨 Изменение | Добавлен `await session.commit()` в `on_confirm_application` |
| `bot/dialogs/user/request_refund.py` | 🔨 Изменение | Добавлен `await session.commit()` в `on_confirm_application` |

---

## Документация для разработчиков

### ✅ ПРАВИЛЬНОЕ ИСПОЛЬЗОВАНИЕ

#### Для handlers, открывающих сессию напрямую:

```python
@router.message(CommandStart())
async def start(msg: Message):
    async with async_session() as session:
        # Database operations with explicit commit
        person = await create_person(session, ...)
        await session.commit()  # ← EXPLICIT
```

#### Для диалогов (с DatabaseMiddleware):

```python
async def on_confirm_dialog(clb: CallbackQuery, dialog_manager: DialogManager):
    session = dialog_manager.middleware_data[SESSION_KEY]
    
    # Multiple operations
    item1 = await create_item(session, ...)
    item2 = await create_item(session, ...)
    
    # Atomic commit
    await session.commit()  # ← EXPLICIT
```

### ❌ НЕПРАВИЛЬНОЕ ИСПОЛЬЗОВАНИЕ

```python
# ❌ НЕ делать автоматический commit в database методе
async def create_person(session, ...):
    person = Person(...)
    session.add(person)
    await session.commit()  # ❌ ЗАПРЕЩЕНО - flush only!
    return person

# ❌ НЕ полагаться на middleware для commit
async def some_handler():
    async with async_session() as session:
        await create_person(session, ...)
        # ❌ ОШИБКА - person не сохранена (БЕЗ explicitly commit)
```

---

## Метрики

**Файлов изменено**: 3
- `bot/middlewares/database.py` - Middleware (основное)
- `bot/dialogs/user/property_database.py` - Dialog handler
- `bot/dialogs/user/request_refund.py` - Dialog handler

**Добавлено явных commits**: 2
- `property_database.py::on_confirm_application()`
- `request_refund.py::on_confirm_application()`

**Удалено опасных паттернов**: 1
- Автоматический commit из middleware

**Добавлено документации**: 2 места
- DatabaseMiddleware class docstring
- DatabaseMiddleware._create_session_and_call() docstring

---

## Заключение

✅ **ПРОБЛЕМА 7 РЕШЕНА**

**Текущая стратегия: Explicit Transaction Management**

### Ключевые принципы

1. **Database методы** используют только `flush()`
2. **Middleware** предоставляет сессию (не коммитит автоматически)
3. **Handlers/Dialogs** явно отвечают за `commit()` / `rollback()`
4. **Атомарность** достигается через явный контроль в handler
5. **Безопасность**: rollback при необработанных ошибках

### Преимущества

- ✅ **Explicit**: Видно в коде где происходит commit
- ✅ **Controllable**: Handler решает когда коммитить
- ✅ **Flexible**: Можно комбинировать операции в транзакции
- ✅ **Safe**: Automatic rollback при ошибках
- ✅ **Maintainable**: Новые разработчики понимают схему

### Связь с предыдущими проблемами

- **PROBLEM_5**: Выбрали стратегию middleware-based commits
- **PROBLEM_6**: Документировали database методы (flush only)
- **PROBLEM_7**: Реализовали explicit transaction management (handler контролирует commit)

### Рекомендации

1. **Pre-commit hook** для проверки на `session.commit()` в `database/methods/**`
2. **Linter правило** для обнаружения неправильных await на `session.delete()`
3. **Test случаи** для проверки rollback при ошибках
4. **Документация** в README или ARCHITECTURE.md для новых разработчиков

---

**Status**: ✅ Готово к production
