# Реализация функционала "База имущества"

## Описание

Реализован функционал "База имущества" для Telegram-бота, позволяющий пользователям:
- Просматривать доступное имущество по категориям
- Создавать заявки на использование имущества LBG
- Получать уведомления о принятии заявки

## Команда бота

- `/property_database` - запускает диалог "База имущества"

## Структура изменений

### 1. Новые файлы

#### State Machine
- **`bot/state_machines/property_database.py`**
  - Определяет все состояния диалога базы имущества
  - Состояния: `MAIN_MENU`, `SHOW_LIST_CATEGORY`, `SHOW_LIST_ITEMS`, `CREATE_APPLICATION`, `INPUT_NAME`, `INPUT_PURPOSE`, `SELECT_ITEMS`, `SELECT_ITEMS_FROM_CATEGORY`, `REVIEW_APPLICATION`, `CONFIRM_APPLICATION`

#### Модель данных
- **`bot/database/models/application.py`**
  - Модель `Application` для хранения заявок на использование имущества
  - Поля: `id`, `applicant_name`, `purpose`, `status`, `created_at`, `person_id`
  - Промежуточная таблица `application_item` для связи многие-ко-многим с `Item` и хранения количества

#### Методы работы с БД
- **`bot/database/methods/application/__init__.py`**
- **`bot/database/methods/application/create.py`**
  - `create_application()` - создание новой заявки с предметами и их количествами
- **`bot/database/methods/application/read.py`**
  - `get_application_by_id()` - получение заявки по ID

#### Диалог
- **`bot/dialogs/user/property_database.py`**
  - Реализация диалога с 9 окнами
  - Обработка всех действий пользователя
  - Интеграция с БД и отправка уведомлений

### 2. Измененные файлы

#### Конфигурация
- **`bot/env.py`**
  - Добавлен `TREASURER_ID` для отправки уведомлений казначею

#### Обработчики команд
- **`bot/handlers/commands.py`**
  - Обновлен обработчик `/property_database` для запуска диалога
  - Добавлен импорт `PropertyDatabase`

#### Регистрация диалогов
- **`bot/dialogs/user/main.py`**
  - Добавлен `property_database_dialog` в роутер

#### Middleware
- **`bot/middlewares/__init__.py`**
  - Добавлен экспорт `SESSION_KEY` для доступа к сессии БД в диалогах

#### Методы работы с категориями
- **`bot/database/methods/category/read.py`**
  - Добавлен метод `get_all_categories()` - получение всех категорий
- **`bot/database/methods/category/__init__.py`**
  - Добавлен экспорт `get_all_categories`

#### Методы работы с предметами
- **`bot/database/methods/item/read.py`**
  - Добавлен метод `get_items_by_category_id()` - получение предметов по категории
- **`bot/database/methods/item/__init__.py`**
  - Добавлен экспорт `get_items_by_category_id`

#### Модели данных
- **`bot/database/models/item.py`**
  - Добавлена связь `applications` для связи многие-ко-многим с `Application`
- **`bot/database/models/person.py`**
  - Добавлена связь `applications` для связи один-ко-многим с `Application`
- **`bot/database/models/__init__.py`**
  - Добавлен импорт `Application`

#### Локализация
- **`bot/l10n/ru/main.ftl`**
  - Добавлены строки локализации:
    - `property-database-main-menu` - текст главного меню
    - `show-list-button` - кнопка "Показать список"
    - `create-application-button` - кнопка "Оформить заявку"

## Структура базы данных

### Таблица `applications`
```sql
CREATE TABLE applications (
    id INTEGER PRIMARY KEY,
    applicant_name VARCHAR(255) NOT NULL,
    purpose VARCHAR(500) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at DATETIME NOT NULL,
    person_id INTEGER NOT NULL,
    FOREIGN KEY (person_id) REFERENCES persons(id)
);
```

### Промежуточная таблица `application_items`
```sql
CREATE TABLE application_items (
    application_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    PRIMARY KEY (application_id, item_id),
    FOREIGN KEY (application_id) REFERENCES applications(id),
    FOREIGN KEY (item_id) REFERENCES items(id)
);
```

## Поток работы функционала

### 1. Главное меню
При вызове команды `/property_database` пользователь видит:
- Информационное сообщение о функционале
- Две кнопки:
  - **"Показать список"** - просмотр доступного имущества
  - **"Оформить заявку"** - создание заявки

### 2. Просмотр списка имущества
- Пользователь выбирает категорию
- Отображается таблица доступного имущества с колонками:
  - Наименование
  - Количество (с единицей измерения)

### 3. Создание заявки
Пользователь заполняет форму:
1. **Имя** - ввод имени заявителя
2. **Цель** - ввод цели взятия имущества
3. **Предметы** - выбор предметов из категорий
   - Выбор категории
   - Выбор предметов из категории (количество увеличивается при каждом нажатии)
   - Можно вернуться к выбору категории для добавления других предметов

### 4. Просмотр и подтверждение заявки
- Отображается итоговая информация:
  - Имя заявителя
  - Цель
  - Список выбранных предметов с количествами
- Кнопка "Подтвердить отправку заявки"

### 5. Подтверждение
- Заявка сохраняется в БД
- Казначей получает уведомление (если `TREASURER_ID` настроен)
- Пользователь видит сообщение об успешной отправке

## Настройка окружения

Добавила в `.env` файл:
```env
TREASURER_ID=telegram-id # Telegram ID казначея для получения уведомлений
```

## Миграции базы данных

Для работы функционала необходимо создать миграцию Alembic:

```bash
cd bot
alembic revision --autogenerate -m "Add applications table"
alembic upgrade head
```

Миграция создаст:
- Таблицу `applications`
- Промежуточную таблицу `application_items`
- Связи с существующими таблицами `persons` и `items`

## API методов

### `create_application()`
```python
async def create_application(
    session: AsyncSession,
    person_id: int,
    applicant_name: str,
    purpose: str,
    items_with_quantities: Dict[int, int],  # {item_id: quantity}
) -> Application
```

### `get_all_categories()`
```python
async def get_all_categories(
    session: AsyncSession,
) -> List[Category]
```

### `get_items_by_category_id()`
```python
async def get_items_by_category_id(
    session: AsyncSession,
    category_id: int,
) -> List[Item]
```

## Уведомления

При создании заявки казначей получает сообщение с информацией:
- Имя заявителя
- Цель взятия имущества
- ID заявки

Уведомление отправляется только если `TREASURER_ID` настроен в `.env`.

## Статусы заявок

Заявки имеют статус `pending` по умолчанию. Потом можно добавить:
- `approved` - одобрена
- `rejected` - отклонена
- `completed` - выполнена

## Зависимости

Функционал использует существующие зависимости проекта:
- `aiogram` и `aiogram-dialog` для диалогов
- `sqlalchemy` для работы с БД
- `fluent.runtime` для локализации

## Будущие улучшения

Возможные улучшения:
- Добавление возможности редактирования количества предметов в заявке
- Добавление возможности удаления предметов из заявки
- Добавление истории заявок пользователя
- Добавление админ-панели для управления заявками
- Добавление фильтров и поиска по предметам
- Добавление возможности указания даты возврата имущества

