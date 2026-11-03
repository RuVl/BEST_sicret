# Todo: правки AmneziaWG по ревью #67

План: [`tasks/plan.md`](plan.md). Спецификация: [`docs/specs/awg-review-fixes.md`](../docs/specs/awg-review-fixes.md).
Общая проверка каждой задачи: `make test-bot` и `make lint` зелёные; одна задача — один коммит.

## Phase 1: `config-hide`

- [x] **Task 1: учёт отправленных копий конфига** (M)
  - Acceptance:
    - `PendingHides` хранит по токену метаданные и множество `message_id` (Redis: hash + set на токен; без Redis — в памяти процесса, чтобы таймер работал и в dev).
    - `memory_media.put(..., owner=token)`; `MemoryMediaMessageManager` после отправки/редактирования сообщения с `memory://`-медиа сообщает «медиа X ушло сообщением Y» подписчику хранилища — сам менеджер о скрытиях не знает; подписчик (реестр скрытий) регистрирует `message_id` за владельцем.
  - Verify: `tests/test_pending_hides.py` (fake Redis: add / add_message / take / remove), `tests/test_memory_media.py` (менеджер регистрирует id, в т.ч. при повторной отправке по file_id).
  - Files: `bot/includes/pending_hides.py`, `bot/includes/memory_media.py`, `bot/tests/test_pending_hides.py`, `bot/tests/test_memory_media.py`
  - Depends: —

- [x] **Task 2: скрытие напрямую и его жизненный цикл** (M)
  - Acceptance:
    - `hide_config(bot, token)` удаляет все учтённые сообщения; запись снимается только при успехе или финальной ошибке Telegram («not found» / «can't be deleted»); иная ошибка — запись остаётся, warning в лог.
    - Отмена таймера (остановка бота) запись не снимает; «Готово» скрывает сразу и гасит таймер.
    - Скрытие при старте — из `dp.startup` после `setup_dialogs`, без `BgManager`; окно у пользователя перерисовывается best-effort.
  - Verify: `tests/test_config_hide.py` — 4 сценария ревьюера (отмена, ошибка удаления, «not found», старт с записями) на fake Bot/Redis; репро `real_startup.py` из scratchpad не падает.
  - Files: `bot/includes/config_hide.py` (новый), `bot/dialogs/user/vpn_awg.py`, `bot/run.py`, `bot/dialogs/main.py`, `bot/tests/test_config_hide.py`
  - Depends: 1

- [x] **Task 3: реплики в окне конфига** (S)
  - Acceptance: `MessageInput` в окне `AWG_CONFIG` ставит `ShowMode.NO_UPDATE` — окно не перерисовывается и копия не отправляется; сообщение пользователя не трогаем.
  - Verify: ручная проверка на тестовом боте (текст, стикер, фото поверх конфига); если копия всё же отправится — её учтёт Task 1 и скроет Task 2.
  - Files: `bot/dialogs/user/vpn_awg.py`
  - Depends: 2

## Phase 2: `dialog-races`

- [ ] **Task 4: изоляция событий в `Dispatcher`** (S)
  - Acceptance: `Dispatcher` создаётся фабрикой с `events_isolation=SimpleEventIsolation()`; два одновременных клика по кнопке одного окна обрабатываются последовательно на свежем контексте. Комментарий «апдейты не сериализуются» исправлен.
  - Verify: `tests/test_event_isolation.py` — два параллельных клика через `aiogram_dialog.test_tools.BotClient` и хранилище с копированием данных (как Redis) дают оба обновления; тот же тест без изоляции падает.
  - Files: `bot/run.py`, `bot/dialogs/user/vpn_awg.py`, `bot/tests/test_event_isolation.py`
  - Depends: —

- [ ] **Task 5: удаление без доступа; идемпотентность EDIT-хэндлеров** (S)
  - Acceptance: «Да, удалить» при закрытом доступе → `vpn-awg-denied-alert` и выход в список; повторный вызов `on_delete_confirmed`, `on_toggle_qr`, `on_restore` безопасен.
  - Verify: тест хэндлера с fake `DialogManager`.
  - Files: `bot/dialogs/user/vpn_awg.py`, `bot/tests/test_awg_dialog.py`
  - Depends: 4

## Phase 3: `panel-client`

- [ ] **Task 6: тело update и валидация ответов** (S)
  - Acceptance: `update_body()` шлёт поля в типах `model.Client` 3x-ui (`allowedIPs` — список; сверить остальные поля с исходником из `scratchpad/xui`); `ValidationError` в `get_client_details`/`get_traffic` → `XuiError`.
  - Verify: `test_vpn_schemas.py` — фикстура с реальным строковым `allowedIPs`; тест на `null` в `tunnelAllowedIPs` → `XuiError`.
  - Files: `bot/includes/vpn/schemas.py`, `bot/includes/vpn/client.py`, `bot/tests/test_vpn_schemas.py`, `bot/tests/test_vpn_service.py`
  - Depends: —

- [ ] **Task 7: `skipped` и суспенд-джоб** (S)
  - Acceptance: непустой `skipped` в ответе bulk → `XuiError` с перечнем; пропущенные не помечаются `revoked`/`suspended`; суспенд-джоб коммитит каждого до уведомления, ошибка одного не обрывает прогон.
  - Verify: тесты клиента (ответ с `skipped`) и джоба (fake клиент: один падает, остальные помечены и уведомлены по разу).
  - Files: `bot/includes/vpn/client.py`, `bot/jobs/suspend_awg.py`, `bot/tests/test_vpn_service.py`, `bot/tests/test_awg.py`
  - Depends: 6

## Phase 4: `device-identity`

- [ ] **Task 8: `ensure_peer` подхватывает клиента** (S)
  - Acceptance: при смене имени сначала ищется клиент под новым именем и подхватывается; сбой после `create_peer` + повтор → конфиг, а не «email already in use».
  - Verify: `test_awg.py` — сценарий `sim_ensure_peer.py` (fake клиент, откат сессии между попытками).
  - Files: `bot/includes/awg/service.py`, `bot/tests/test_awg.py`
  - Depends: 7

- [ ] **Task 9: экранирование и названия** (S)
  - Acceptance: `escape_mdv2` экранирует `\`; все вызывающие проверены (`grep escape_mdv2`); ZWJ/вариационные селекторы в названии разрешены, лимит — в кодовых точках (колонка `String(32)`); ошибки «длина» и «недопустимые символы» — разными текстами.
  - Verify: тесты на `PC\-1`, `Ноут\`, `👨‍💻 Работа`, 33 символа, управляющий символ.
  - Files: `bot/utils/escape.py`, `bot/includes/awg/identity.py`, `bot/dialogs/user/vpn_awg.py`, `bot/l10n/ru/vpn.ftl`, `bot/tests/test_awg.py`
  - Depends: —

## Checkpoint B
- [ ] `make test-bot`, `make lint`; двойной тап по платформе на тестовом боте → одно устройство, один клиент

## Phase 5: `person-username` + `cli-admin`

- [ ] **Task 10: уникальный ник** (M)
  - Acceptance: миграция обнуляет дубли (без учёта регистра) и создаёт частичный уникальный индекс `lower(telegram_username)`; `claim_username()` в репозитории снимает ник с других и ставит текущему; `get_or_create_person` пишет и `None`; `find_person_by_handle()` — `@username`/ID.
  - Verify: `make migration`-ревизия руками проверена; `make migrate` на локальной БД с подготовленными дублями; `make downgrade` возвращает индекс как был; unit-тест разбора handle.
  - Files: `packages/db/best_db/models/person.py`, `packages/db/best_db/migrations/versions/<rev>_unique_person_username.py`, `bot/database/methods/person/{get,set,__init__}.py`
  - Depends: —

- [ ] **Task 11: CLI-каркас и подтверждение** (M)
  - Acceptance: `cli/common.py` (CliError, describe `ФИО (tg …)`/`tg …`, `confirm`, `send_bot`, `run`); `awg-grant`/`awg-revoke` печатают, что сделают, и спрашивают `Вы уверены [y/n]: `; `n`/EOF — без изменений; «Уведомление отправлено» — только при успехе.
  - Verify: тесты `describe` и `confirm` (y, yes, n, пусто, EOF); ручной прогон в контейнере.
  - Files: `bot/cli/common.py` (новый), `bot/cli/awg.py`, `bot/tests/test_cli.py`
  - Depends: 10

- [ ] **Task 12: убрать `awg-announce`** (S)
  - Acceptance: удалены `cmd_announce`, `mark_announced`, `vpn-awg-announce`, цель Makefile; миграция удаляет `awg_access.announced_at` (downgrade возвращает колонку).
  - Verify: `make migrate` / `make downgrade`; `test_l10n_keys.py` зелёный; `grep announce` пуст.
  - Files: `bot/cli/awg.py`, `bot/database/methods/awg_access/{set,__init__}.py`, `packages/db/best_db/models/awg_access.py`, `packages/db/best_db/migrations/versions/<rev>_drop_awg_announced_at.py`, `Makefile`, `bot/l10n/ru/vpn.ftl`
  - Depends: 11

- [ ] **Task 13: `make broadcast`** (M)
  - Acceptance: `group=` (all/members/board/awg/vless, объединение) и `to=` (`@username`/ID вперемешку), без обоих — подсказка; превью текста и списка, `[y/n]`; ошибка разметки на первом сообщении — стоп; не дошедшие — строкой для `to=`; ≤10 сообщений/с; Makefile копирует файл через `docker compose cp`.
  - Verify: тесты разбора `group`/`to`, объединения без дублей, неизвестной группы; ручная рассылка себе (`to=<свой id>`).
  - Files: `bot/database/methods/person/audiences.py` (новый), `bot/cli/broadcast.py` (новый), `Makefile`, `bot/tests/test_cli.py`
  - Depends: 11

## Checkpoint C
- [ ] `make awg-revoke`/`awg-grant`/`broadcast` вручную: `n`, `y`, неизвестная группа, ненайденный ник

## Phase 6: `settings-qr`

- [ ] **Task 14: `ENABLED` и endpoint** (S)
  - Acceptance: `settings.awg.ENABLED` ложно без `XUI_BASE_URL`/`XUI_API_TOKEN` (лог старта предупреждает); `_check_endpoint` отклоняет `localhost`, `host.docker.internal`, имена без точки; комментарий у `extra_hosts` актуален.
  - Verify: тесты настроек (env через monkeypatch) и `_check_endpoint`.
  - Files: `bot/env.py`, `bot/includes/awg/<модуль с _check_endpoint>`, `docker-compose.yaml`, `bot/tests/test_awg.py`
  - Depends: —

- [ ] **Task 15: урезанный QR для Android** (M)
  - Acceptance: `IssuedConfig(text, qr_png, qr_excluded, excluded_total)`; файл — полный список; QR — максимальный префикс, который влезает; подпись QR «в QR только N из M исключений, полный список — в файле» при урезании; кнопка QR у Android есть всегда.
  - Verify: тест на реальном `excluded_apps()` — QR строится, N < M, N максимально (N+1 не влезает); iOS — без урезания.
  - Files: `bot/includes/awg/qr.py`, `bot/includes/awg/service.py`, `bot/dialogs/user/vpn_awg.py`, `bot/l10n/ru/vpn.ftl`, `bot/tests/test_awg_platform.py`
  - Depends: 2, 8

## Phase 7: `ui-compact`

- [ ] **Task 16: раскладка и клиенты** (S)
  - Acceptance: раскладка из спецификации; ссылки WG Tunnel / AmneziaWG / App Store (ссылка WG Tunnel проверена), APK убран; `vpn-awg-hint` под WG Tunnel.
  - Verify: `test_l10n_keys.py`; скриншоты окон с тестового бота в PR.
  - Files: `bot/dialogs/user/vpn_awg.py`, `bot/l10n/ru/vpn.ftl`
  - Depends: 5, 15

## Phase 8: `cleanup`

- [ ] **Task 17: мелочи из ревью** (S)
  - Acceptance: общий помощник «выбыл из LBG»; `notify()` — в `includes/notify.py` с ключом лога `notify-failed`; строки сводки суспенд-джоба — через Fluent; мёртвый `try/except` и неиспользуемые ключи `dialog_data` убраны.
  - Verify: `make test-bot`, `make lint`, `grep vpn-revoke-notify-failed` пуст.
  - Files: `bot/includes/notify.py` (новый), `bot/jobs/{revoke_vpn,suspend_awg}.py`, `bot/dialogs/user/vpn_awg.py`, `bot/l10n/ru/vpn.ftl`
  - Depends: все

## Checkpoint: Complete
- [ ] `make test-bot`, `make lint`; `code-review high` по ветке без блокеров
- [ ] Ручной чек-лист в PR пройден на тестовом боте
- [ ] PR в `dev` слит; #67 сливается merge-коммитом
