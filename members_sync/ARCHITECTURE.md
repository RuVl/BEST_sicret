# members_sync — архитектура

Отдельный сервис, который **раз в сутки (03:00 МСК)** синхронизирует базу участников
из Google Sheets в Postgres. Google-таблица — **единственный источник истины**.
Сервис устойчив к изменениям структуры таблицы, не теряет данные и сообщает об
ошибках парсинга прямо в таблице (заметками к ячейкам).

> Решения, согласованные с владельцем (RuVl):
> 1. Ошибки парсинга → **заметки к ячейкам** (gspread notes), а не threaded-комментарии.
> 2. Пропавшие из таблицы участники **не удаляются** — им меняется статус на `ex`/`inactive`
>    (обычно человек просто переезжает на лист *Ex-members*).
> 3. Схема БД — **одна таблица `lbg_members` + сырой snapshot (JSONB)** (модель `LbgMember` в `best_db`).
> 4. Ключ сопоставления (upsert) — **email `@best-eu.org`**, fallback — нормализованное русское ФИО.

---

## 1. Источник данных: три листа, три раскладки

| Лист (worksheet) | CSV | Раскладка колонок | Дефолтная категория |
|---|---|---|---|
| `Database of Members` | page1 | **раскладка A** | активные (board/full/baby/observer) |
| `Alumni+Former+abroad+guests+inactive` | page2 | **раскладка B** | alumni/former/abroad/guest/inactive |
| `Ex-members` | page3 | **раскладка B** | ex-full / ex-baby |

Ключевые наблюдения, диктующие архитектуру:

1. **Колонки различаются между листами.** На page1 «ВКонтакте/Telegram» — колонка 3,
   нет колонки «Место работы», иной порядок Local/International/Events. На page2/3
   «ВКонтакте/Facebook» — колонка 9, есть «Место работы», другой порядок.
   → **Нельзя парсить по фиксированным индексам.** Колонки определяются по тексту заголовка.
2. **Один участник = две физические строки.** Строка 1 — ФИО на русском + большинство
   полей; строка 2 — ФИО на английском, Telegram/Facebook, и **учебная группа**
   (код вида `3733806/20102`) в колонке «Факультет, группа».
3. **Секции-заголовки** (`BOARD`, `FULL MEMBERS`, `BABY MEMBERS`, `OBSERVERS`, `ALUMNI`,
   `EX-FULL MEMBERS`, `EX-BABY MEMBERS` …) идут отдельной строкой: колонка 0 пустая,
   колонка 1 содержит название секции. Секция задаёт категорию членства.
4. **Внизу листа** — блок статистики и пустые строки. Конец данных детектируется
   (несколько пустых строк подряд / строка «Statistics:» / строка, не похожая на участника).
5. **Данные грязные:** телефоны в 5+ форматах, даты в т.ч. в американском `m/d/y`
   (`11.16.1982`, `8/30/1990`), ФИО иногда переставлены (рус. в строке 2), пустые ячейки,
   несколько телефонов/почт в одной ячейке. Парсер обязан **деградировать, а не падать**.

---

## 2. Принципы устойчивости (что делает парсинг «стабильным к изменениям»)

1. **Маппинг колонок по заголовкам, а не по индексам.** Для каждого листа задан
   `SheetSpec`: список канонических полей, каждое поле — набор алиасов заголовка
   (регистронезависимо, толерантно к пробелам/переносам/`ё`/`е`). На старте читаем
   строку(и) заголовка и резолвим `column_index → canonical_field`. Перестановка или
   переименование колонки не ломает парсер, пока заголовок узнаваем.
2. **Конфигурация листа отделена от кода.** `SheetSpec` описывает: строки заголовка,
   высоту записи (2 строки), какие поля берутся из строки 1, а какие из строки 2,
   правило детекта секции, дефолтную категорию листа.
3. **Парсинг по полям с захватом ошибок.** У каждого канонического поля — свой
   нормализатор `raw_str -> (value, ParseIssue | None)`. Нормализатор **никогда не бросает
   исключение** на плохих данных: возвращает `value=None` + человекочитаемую `ParseIssue`
   с координатой ячейки (A1). Запись всё равно синхронизируется.
4. **Сырой snapshot.** В каждой записи хранится `raw` (JSONB) — словарь
   `canonical_field -> raw_string` (обе строки) + метаданные источника (лист, gid, номера
   строк, `parsed_at`). Гарантирует отсутствие потери данных и возможность ре-парсинга
   без обращения к API.
5. **Никаких DB-enum.** Категории/статусы хранятся строками (известные значения
   задокументированы). Появление новой секции в таблице **не требует миграции**.
6. **Идемпотентность.** Полный прогон над неизменной таблицей не создаёт дубликатов и
   изменений (кроме `last_synced_at`). Заметки об ошибках перезаписываются/снимаются.

---

## 3. Структура каталога

```
members_sync/
├── ARCHITECTURE.md            # этот файл
├── README.md                  # как запускать
├── Dockerfile                 # образ сервиса (uv sync; best_db через additional_contexts)
├── pyproject.toml / uv.lock   # зависимости (best_db editable + gspread/sqlalchemy/…)
├── .env / .env.dist           # SPREADSHEET_KEY, креды БД, флаги
├── service_account.json       # gitignored
├── run.py                     # entrypoint: один прогон или cron-режим
├── env.py                     # конфиг (в стиле bot/env.py)
├── logger.py                  # structlog, как в боте
│
├── database/                  # свой engine + методы; модели/alembic — в packages/db
│   ├── main.py                # engine + async_session (+ create_schema для dev)
│   └── methods/member/        # upsert / get / deactivate_missing (над LbgMember)
│
├── sheets/                    # слой Google Sheets
│   ├── client.py              # gspread service-account
│   ├── spec.py                # SheetSpec + алиасы заголовков (раскладки A и B)
│   ├── column_mapper.py       # заголовок → canonical_field (fuzzy)
│   ├── record_reader.py       # сборка 2-строчных записей + секции + конец данных
│   └── notes.py               # запись/снятие заметок об ошибках (batch)
│
├── parsing/                   # доменная логика разбора
│   ├── fields.py              # перечень канонических полей
│   ├── normalizers.py         # phone/date/period/vk/telegram/gender/group…
│   ├── issues.py              # ParseIssue, сборщик ошибок с A1-координатами
│   └── member_builder.py      # RawRecord -> ParsedMember (+ список issues)
│
├── sync/
│   ├── service.py             # оркестратор всего прогона
│   └── report.py              # запись .md-отчёта о прогоне
│
├── tests/                     # юнит-тесты (normalizers + pipeline), make test
│
└── output/
    └── members.json           # отладочный дамп (gitignored)
```

## 4. Поток выполнения (один прогон)

```
run.py
 └─ sync.service.run()
     1. SheetsClient.open(SPREADSHEET_KEY)
     2. values_batch_get(все подходящие листы)              # 1 API-запрос на все листы
     3. для каждого загруженного листа:
          a. ColumnMapper.resolve(header_rows, SheetSpec)   # колонки по заголовкам
          b. RecordReader.iter_records()                    # 2-строчные записи + секция
          c. для каждой записи: MemberBuilder.build()       # -> ParsedMember + issues
     4. дедуп по identity_key между листами (precedence: active > alumni > ex)
     5. upsert в БД (match по identity_key), фиксация first/last_seen, статуса
     6. deactivate_missing(): кто был в БД, но не встретился в прогоне -> статус ex/inactive
     7. NotesWriter.flush(): записать/снять заметки об ошибках (если WRITE_SHEET_NOTES)
     8. ReportWriter: записать отчёт о прогоне (.md) + output/members.json
```

API-бюджет на чтение: **1 `worksheets()` (метаданные) + 1 `values_batch_get` (значения всех
листов) + 1 `fetch_sheet_metadata` (заметки всех листов)** + 1 `batch_update` на запись заметок.
Раньше чтение шло по `get_all_values()`/`get_notes()` на каждый лист — N round-trip'ов, что
упиралось в латентность и rate-limit Google API. Ключевые шаги обёрнуты в тайминг-логи
(`elapsed_s`), чтобы видеть, куда уходит время прогона.

---

## 5. Идентичность и upsert

- `identity_key`:
  - если есть `best_email` (`*@best-eu.org`) → `lower(best_email)`;
  - иначе → `normalized_full_name_ru` (нижний регистр, схлопнутые пробелы, `ё→е`).
- `lbg_members.identity_key` — `UNIQUE`, индекс.
- Upsert: найти по `identity_key` → обновить; иначе вставить.
- Поля жизненного цикла: `first_seen_at`, `last_seen_at`, `last_synced_at`,
  `removed_from_sheet_at`, `is_active`.
- **Дубликаты между листами:** один человек может «зависнуть» сразу на двух листах.
  Приоритет: `Database of Members` (active) > Alumni > Ex-members. Берём авторитетную
  строку по приоритету, остальным вхождениям ставим заметку «дубликат между листами».

### Членство

Секция листа → `Membership` (`parsing/fields.py`): категория строкой плюс два независимых
флага. `is_active` — может брать таски группы; `is_excluded` — из группы исключён.
Alumni и former не активны, но и не исключены: доступ к ресурсам бота у них сохраняется.

| Источник | Секция | `membership_category` | `is_active` | `is_excluded` |
|---|---|---|---|---|
| page1 | BOARD | `board` | ✔ | |
| page1 | FULL MEMBERS | `full_member` | ✔ | |
| page1 | BABY MEMBERS | `baby_member` | ✔ | |
| page1 | OBSERVERS | `observer` | ✔ | |
| page2 | ALUMNI / Former / Inactive | `alumni`/`former`/`inactive` | | |
| page2 | Abroad / Guest | `abroad`/`guest` | ✔ | |
| page3 | EX-FULL MEMBERS | `ex_full_member` | | ✔ |
| page3 | EX-BABY MEMBERS | `ex_baby_member` | | ✔ |
| — (пропал из всех листов) | — | сохраняется прошлая | | без изменений |

`deactivate_missing`: запись, которой не было в текущем прогоне, получает
`is_active=false` и `removed_from_sheet_at=now()`. `is_excluded` не трогается —
пропажа из таблицы и исключение из группы разные события. Данные **не удаляются**.

При дедупе одного человека между листами побеждает запись с большим
`membership_precedence`: активная > alumni > former/inactive > исключённая.

---

## 6. Модель `LbgMember` (таблица `lbg_members`)

Идентификация / служебное: `id` PK, `identity_key` UNIQUE,
`first_seen_at`, `last_seen_at`, `last_synced_at`, `removed_from_sheet_at`,
`is_active`, `is_excluded`, `created_at`, `updated_at`.

Источник: `source_sheet`, `source_section`, `source_row_start`, `source_row_end`,
`raw` (JSONB).

Данные участника:
`full_name_ru`, `full_name_en`, `gender`,
`best_email`, `personal_email`,
`birthday` (date) + `birthday_raw`,
`phone` (нормализ.) + `phone_raw`,
`vk_url`, `telegram`, `facebook`, `instagram`,
`faculty`, `study_group`,
`home_address`, `dormitory`,
`angel_name`,
`status_field` (роли/должность как в таблице),
`active_since` (date) + `active_since_raw`, `active_till` (date) + `active_till_raw`,
`local_involvement`, `international_involvement`, `best_events`, `workplace`,
`membership_category`.

Принцип: типизированное поле + `*_raw` для неоднозначных значений; `raw` JSONB как
полный сырой слепок. Потеря данных исключена.

---

## 7. Нормализаторы (см. `parsing/normalizers.py`)

- **phone** — оставить цифры; `8→7`, `+7`, 10-значный → `+7…`; первый номер в `phone`,
  весь текст в `phone_raw`; несколько номеров допустимы.
- **birthday/date** — форматы `dd.mm.yyyy`, `d.m.yyyy`, `yyyy-mm-dd`, и **американские**
  `m/d/yyyy`, `m.d.yyyy` (`11.16.1982`, `8/30/1990`). При `day>12` — переставить;
  при неоднозначности/ошибке → `None` + `ParseIssue`. Сырое значение всегда в `*_raw`.
- **active period** — `«March 2024»`, `«March 2015 - May 2018»`, `«Sep 22'»`,
  `«Sep 2011 - Feb 2013»` → `active_since` / `active_till` (+ raw).
- **vk / telegram / facebook / instagram** — привести к url или `@handle`.
- **gender** — `Female/Male` → `female/male`.
- **study_group** — код `3733806/20102` валидируется мягко (иначе raw + issue).

---

## 8. Сообщение об ошибках — заметки к ячейкам

- `NotesWriter` копит `(sheet, A1, text)` и пишет батчем (`spreadsheets.batchUpdate`
  → `repeatCell`/`updateCells` с полем `note`).
- Текст с маркером `🤖 [sync]…`, чтобы:
  - не затирать человеческие заметки;
  - **снимать** свои заметки, когда ошибка исправлена (idempotent).
- Управляется флагом `WRITE_SHEET_NOTES` (по умолчанию `false` для безопасных прогонов).
- Требует у сервис-аккаунта право редактирования таблицы.

---

## 9. Отчётность и статус работ (.md)

- `MEMBERS_SYNC_STATUS.md` (корень репо) — **трекер разработки** сервиса (чек-лист
  этапов), ведётся вручную.
- `members_sync/last_sync_report.md` (gitignored) — **отчёт о последнем прогоне**:
  время, счётчики по листам/статусам, inserted/updated/deactivated, список ошибок
  с координатами ячеек. Пишется сервисом каждый прогон.
- `members_sync/output/members.json` — отладочный дамп распарсенных участников.

---

## 10. Запуск и расписание

- `run.py` — **одноразовый прогон** (`RUN_MODE=once`, по умолчанию): выполнил sync и вышел.
  Подходит для запуска внешним планировщиком (host cron / k8s CronJob / Ofelia) в 03:00 МСК.
- `RUN_MODE=cron` — контейнер живёт постоянно и сам запускает sync по расписанию
  (apscheduler, `CRON_HOUR=3`, `TZ=Europe/Moscow`).
- Dockerfile собирает образ; в `docker-compose.yaml` добавляется сервис `members_sync`
  в ту же сеть `best_backend`, та же БД Postgres, что и у бота.

### Схема БД и миграции
Все модели и **единый** alembic вынесены в общий пакет `packages/db` (`best_db`) —
единственный владелец схемы для бота и `members_sync`. `members_sync` импортирует
оттуда `LbgMember`, держит **свой** engine/session (из своего `env`) и в dev-режиме
может создать только свою таблицу (`create_schema`, `AUTO_CREATE_SCHEMA`). В проде
схему накатывает единый alembic (`make migrate` / сервис `db_migrate`). Таблица —
`lbg_members`; есть опциональная связь `Person.lbg_member` для опознавания
участника, написавшего боту.

---

## 11. Известные риски / TODO

- Неоднозначные даты `m/d` vs `d/m` — эвристика + issue; 100% точность недостижима.
- ФИО как fallback-ключ неустойчив к смене фамилии/опечаткам — поэтому приоритет у email.
- Если у участника нет ни `@best-eu.org`, ни личной почты, ни ФИО — запись пропускается
  с ошибкой в отчёт.
- Парные строки: если у участника только одна строка (нет EN-строки) — обрабатываем
  как запись из одной строки, EN-поля пустые.
