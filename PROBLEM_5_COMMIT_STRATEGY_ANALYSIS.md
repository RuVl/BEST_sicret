# ПРОБЛЕМА 5: Анализ стратегии коммита БД

## Резюме проблемы

В проекте отсутствует **единая стратегия работы с database commits**. Разные части кода используют разные подходы к управлению транзакциями, что приводит к:
- Потенциальным потерям данных
- Двойным коммитам в некоторых местах
- Несоответствиям между слоями приложения
- Ошибкам в типах вызовов (await на несинхронные методы)

---

## Выявленные проблемы

### 1. **Несогласованность в слое Database Methods**

#### Проблема 1.1: Разные подходы в create-методах

**Вариант A: Метод `create_person()` - COMMIT внутри метода**
```python
# bot/database/methods/person/create.py
async def create_person(session, telegram_id, full_name):
    person = Person(telegram_id=telegram_id, full_name=full_name)
    session.add(person)
    try:
        await session.commit()  # ❌ Коммит ВНУТРИ метода
    except IntegrityError:
        await session.rollback()
        raise
    return person
```

**Вариант B: Методы `create_application()`, `create_refund()`, `create_place()` и др. - только FLUSH**
```python
# bot/database/methods/application/create.py
async def create_application(session, person_id, applicant_name, purpose, items_with_quantities):
    application = Application(...)
    session.add(application)
    await session.flush()  # ✓ Только flush - предполагается commit снаружи
    await session.refresh(application)
    return application
```

**Проблема**: Две разные стратегии для одного типа операции!

#### Проблема 1.2: Все update-методы используют только FLUSH
```python
# bot/database/methods/person/update.py
async def update_person(session, person, full_name=None, payment_id=None):
    if full_name is not None:
        person.full_name = full_name
    if payment_id is not None:
        person.payment_id = payment_id
    
    await session.flush()  # Только flush, нет commit
    await session.refresh(person)
    return person
```

**Проблема**: Эти методы полагаются на внешний commit, но это не задокументировано.

#### Проблема 1.3: Ошибки в delete-методах

```python
# bot/database/methods/place/delete.py
async def delete_place(session, place):
    await session.delete(place)  # ❌ ОШИБКА: session.delete() не asyncio метод!
    await session.flush()        # ❌ Без commit
```

```python
# bot/database/methods/category/delete.py
async def delete_category(session, category):
    await session.delete(category)  # ❌ Неправильно
    await session.flush()
```

**Проблема**: 
- Метод `.delete()` в SQLAlchemy это NOT coroutine, нельзя его await-ить
- Это вызовет runtime ошибку: "TypeError: 'NoneType' object is not callable"
- Нет commit, данные не сохратяются

### 2. **Несогласованность в обработчиках (handlers)**

#### Проблема 2.1: Handler `start` открывает сессию напрямую и коммитит

```python
# bot/handlers/commands.py - start handler
@router.message(CommandStart())
async def start(msg: Message, l10n: FluentLocalization):
    async with async_session() as session:
        person = await get_person_by_telegram_id(session, msg.from_user.id)
        if person is None:
            full_name = msg.from_user.full_name or ...
            person = await create_person(  # Это метод, который СРАЗУ КОММИТИТ
                session=session,
                telegram_id=msg.from_user.id,
                full_name=full_name,
            )
        # ✓ Контекст выходит, сессия закрывается, но...
        # create_person УЖЕ сделал commit внутри!
```

**Проблема**: 
- Handler использует `async with async_session()` напрямую
- А не полагается на DatabaseMiddleware
- Получается ДВОЙНОЙ commit: один в `create_person`, другой при выходе из контекста
- Несоответствие с диалогами, которые используют middleware

#### Проблема 2.2: Диалоги полагаются на middleware

```python
# bot/dialogs/user/property_database.py - on_confirm_application
async def on_confirm_application(clb, _button, dialog_manager):
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    
    application = await create_application(
        session=session,
        person_id=person.id,
        applicant_name=applicant_name,
        purpose=purpose,
        items_with_quantities=selected_items
    )  # Здесь commit должен сделать middleware ПОСЛЕ завершения хендлера
```

**Проблема**: Диалоги полагаются на middleware, но handler `start` не использует middleware!

### 3. **Параметр-функция ошибка (Bug)**

#### Проблема 3.1: Несоответствие параметров в `create_refund()`

```python
# bot/database/methods/refund/create.py - определение функции
async def create_refund(
    session: AsyncSession,
    name: str,
    customer_id: int,  # Ожидает customer_id
    payment_id: int,
    description: Optional[str] = None,
) -> Refund:
```

```python
# bot/dialogs/user/request_refund.py - вызов функции
refund_request = await create_refund(
    session=session,
    person_id=person.id,  # ❌ Передается person_id, но функция ждет customer_id!
    name=dialog_manager.dialog_data.get('name'),
    ...
)
```

**Проблема**: 
- Имя параметра не совпадает
- Это может вызвать ошибку "unexpected keyword argument"
- Логика работает, но интерфейс запутан

### 4. **Несогласованность в middleware**

```python
# bot/middlewares/database.py
class DatabaseMiddleware(BaseMiddleware):
    async def _create_session_and_call(...):
        async with async_session() as session:
            data[SESSION_KEY] = session
            try:
                result = await handler(event, data)
                await session.commit()  # ✓ Коммит ПОСЛЕ обработчика
                return result
            except Exception:
                await session.rollback()  # ✓ Откат при ошибке
                raise
```

**Проблема**: 
- Middleware правильно использует commit/rollback
- НО поддерживает только handlers с флагом `requires_db=True`
- НО `start` handler НЕ использует middleware! Он открывает сессию напрямую!

---

## Выявленные стратегии

В проекте наблюдаются **2 конфликтующие стратегии**:

### Стратегия 1: Commit внутри database методов
```
Handler -> DatabaseMethod (session.commit()) -> Data saved
```
**Используется в**: `person/create.py`

**Минусы**:
- Сложно обработать ошибки на уровне handler
- Сложно объединить несколько операций в одну транзакцию
- Не позволяет отката всей операции handler при ошибке

### Стратегия 2: Commit в middleware
```
Middleware -> Handler -> DatabaseMethod (session.flush()) -> Middleware (session.commit) -> Data saved
```
**Используется в**: Диалоги с `DatabaseMiddleware`, большинство database методов (use flush только)

**Минусы** (при текущей реализации):
- Handler `start` НЕ использует middleware - создает сессию напрямую!
- Несоответствие между handlers

**Плюсы**:
- Атомарность: вся операция handler либо успешна, либо откатывается
- Единопедчик: один уровень ответственности для commits
- Гибкость: можно объединить несколько DB операций

---

## Рекомендуемое решение

**ВЫБИРАЕМ: Стратегия 2 (Middleware-based commits)**

Причины:
1. Уже реализована в middleware
2. Более гибкая и безопасная
3. Поддерживает атомарность операций
4. Соответствует pattern диалогов

### Требуемые изменения:

#### 1. Скорректировать database методы
- ✅ Все `create_*` методы: оставить только `flush()` и `refresh()`, БЕЗ `commit()`
- ✅ Все `update_*` методы: оставить только `flush()` и `refresh()`, БЕЗ `commit()`  
- ✅ Все `delete_*` методы: FIX - убрать `await` перед `session.delete()`, оставить только `flush()` БЕЗ `commit()`

#### 2. Скорректировать обработчик `start`
- Обернуть логику в DatabaseMiddleware или использовать тот же подход, что и диалоги

#### 3. Исправить параметры `create_refund()`
- Переименовать `customer_id` → `person_id` для соответствия по всему коду

#### 4. Добавить документацию
- Описать использование Strategy 2 в docstring каждого database метода

---

## Раздел: Результаты (ДО ИСПРАВЛЕНИЯ)

### Ошибки в коде:
1. ❌ `await session.delete()` - неправильный синтаксис, вызовет ошибку
2. ❌ Двойной commit при вызове `create_person` из `start` handler
3. ❌ Несоответствие параметров `person_id` vs `customer_id` в refund
4. ❌ Документация отсутствует - разработчикам неясна стратегия

### Потенциальные последствия:
- 🔴 **Высокая**: Потеря данных при delete операциях (await ошибка)
- 🔴 **Средняя**: Неконсистентность при многих операциях подряд
- 🟡 **Низкая**: Запутанность для новых разработчиков

