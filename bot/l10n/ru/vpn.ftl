# Remember to escape some characters for MarkdownV2 syntax:
# https://core.telegram.org/bots/api#markdownv2-style
# Пустая строка обрывает сообщение, поэтому пустые абзацы — через { "" }.

vpn-none = *VLESS\-подписка* \(запасной вариант\)
    { "" }
    Подписки пока нет\. Нажмите «Выпустить» — бот создаст ключ и пришлёт ссылку\.

vpn-active = *VLESS\-подписка активна* \(запасной вариант\)
    { "" }
    Ссылка\-подписка \(нажмите, чтобы скопировать\):
    `{ $url }`
    { "" }
    Трафик за текущий период: { $traffic }

vpn-orphaned = *VLESS\-подписка недействительна* \(запасной вариант\)
    { "" }
    Ключ удалён из панели, старая ссылка больше не работает\.
    Нажмите «Выпустить» — бот создаст новый ключ и пришлёт новую ссылку\.

vpn-disabled = *VLESS\-подписка отключена* \(запасной вариант\)
    { "" }
    Ключ есть, но выключен в панели\. Если это ошибка — напишите VP4HR\.
    { "" }
    Ссылка\-подписка:
    `{ $url }`
    { "" }
    Трафик за текущий период: { $traffic }

vpn-revoked-notice = Ваша VPN\-подписка отключена: вы больше не активный мембер LBG\.
    { "" }
    Если это ошибка — напишите VP4HR\.

vpn-revoke-report = *Автоотзыв VPN\-подписок*
    { "" }
    Отключено: { $revoked }
    Ошибок: { $failed }
    { "" }
    { $details }

# Buttons
vpn-issue-btn = Выпустить
vpn-refresh-btn = Обновить
vpn-handbook-btn = Как подключиться
vpn-handbook-url = https://docs.google.com/document/d/1gcmkXYgEY308JLwmrzNfeBirzJZDPrPx/edit

# Notifications and errors
vpn-issued-alert = Подписка выпущена
vpn-error-alert = Панель VPN недоступна. Попробуйте позже или напишите VP4HR.
vpn-error = Панель VPN недоступна\. Попробуйте позже или напишите VP4HR\.
vpn-access-denied-alert = Доступ к VPN только для активных мемберов LBG
vpn-access-denied = Доступ к VPN только для активных мемберов LBG\.

# === AmneziaWG (основной протокол, открыт всем активным мемберам) ===
# Один конфиг - одно устройство, поэтому ключи заводятся по устройствам.

vpn-awg-hint = *AmneziaWG — основной протокол*
    Откройте «AmneziaWG» и добавьте устройство — бот пришлёт файл и QR\-код\. Если AmneziaWG не подключается, выпустите VLESS\-подписку ниже\.

vpn-awg-devices = *AmneziaWG*
    { "" }
    Нужно приложение AmneziaWG последней версии — ссылки на него под списком\. Старые версии к серверу не подключатся\.
    { "" }
    Один конфиг — одно устройство: на двух устройствах сразу он работать не будет\. Для телефона и ноутбука добавьте два устройства\.
    { "" }
    Устройств: { $used } из { $limit }
    { $devices }

vpn-awg-device-card = *{ $name }*
    { "" }
    Статус: { $status }
    Последнее подключение: { $online }
    Трафик \(скачано / отправлено\): { $traffic }

vpn-awg-name-new = *Новое устройство*
    { "" }
    Напишите название, например «Телефон» или «Ноутбук» \(до { $max } символов\)\.

vpn-awg-name-rename = *Переименование*
    { "" }
    Напишите новое название для «{ $name }» \(до { $max } символов\)\.

vpn-awg-name-invalid-part = Название должно быть от 1 до { $max } символов, попробуйте ещё раз.

vpn-awg-config-caption = *{ $name }* — конфиг AmneziaWG
    { "" }
    Импортируйте файл в приложение AmneziaWG или AmneziaVPN\. Один конфиг — одно устройство\.
    { "" }
    Это ваш личный ключ: сообщение исчезнет через { $minutes } мин или по кнопке «Готово»\.

vpn-awg-qr-caption = *{ $name }* — QR\-код конфига
    { "" }
    Отсканируйте его приложением AmneziaWG на телефоне\.
    { "" }
    Это ваш личный ключ: сообщение исчезнет через { $minutes } мин или по кнопке «Готово»\.

vpn-awg-config-hidden = *Конфиг скрыт*
    { "" }
    Сообщение с ключом убрано из чата\. Если он снова нужен, нажмите «Получить конфиг» в карточке устройства\.

vpn-awg-suspended-hint = Ключи выключены, пока вы не состояли в LBG\. Нажмите «Включить ключи»\.
vpn-awg-panel-error-hint = Панель VPN сейчас недоступна, статус и трафик не показаны\.

vpn-awg-delete-confirm = *Удалить «{ $name }»?*
    { "" }
    Его конфиг перестанет работать\. Новый можно получить, добавив устройство заново\.

vpn-awg-denied = *AmneziaWG недоступен*
    { "" }
    AmneziaWG открыт только активным мемберам LBG\. Если доступ закрыт по ошибке, напишите VP4HR\.

vpn-awg-granted-notice = *Вам открыт AmneziaWG*
    { "" }
    Это основной VPN\-протокол бота\.
    Откройте /start → «VPN\-подписка» → «AmneziaWG» и добавьте устройство\. Один конфиг — одно устройство, всего можно завести { $limit }\.

vpn-awg-announce = *AmneziaWG — новый основной VPN*
    { "" }
    В боте появился AmneziaWG: он работает там, где VLESS не подключается\. Откройте /start → «VPN\-подписка» → «AmneziaWG», добавьте устройство и импортируйте файл или QR\-код в приложение AmneziaWG последней версии\. Один конфиг — одно устройство, всего можно завести { $limit }\.
    { "" }
    Если у вас уже был конфиг AmneziaWG, скоро он перестанет работать — заранее получите новый в карточке устройства\.

vpn-awg-suspended-notice = Ваши ключи AmneziaWG отключены: вы больше не активный мембер LBG\.
    { "" }
    Если это ошибка — напишите VP4HR\.

vpn-awg-suspend-report = *Автоотключение ключей AmneziaWG*
    { "" }
    Отключено: { $revoked }
    Ошибок: { $failed }
    { "" }
    { $details }

# Строки списка и карточки - обычный текст, экранирует код
vpn-awg-device-line-part = { $name }: { $status }
vpn-awg-device-default-name-part = Устройство { $number }
vpn-awg-devices-empty-part = Устройств пока нет. Нажмите «Добавить устройство».
vpn-awg-status-online-part = в сети
vpn-awg-status-inactive-part = давно не подключалось
vpn-awg-status-never-part = ещё не подключалось
vpn-awg-status-disabled-part = выключено
vpn-awg-status-missing-part = нужен новый конфиг — нажмите «Получить конфиг»
vpn-awg-status-unknown-part = статус неизвестен
vpn-awg-handshake-never-part = не было
vpn-awg-traffic-part = { $down } / { $up }
vpn-awg-no-data-part = —

# Кнопки
vpn-awg-btn = AmneziaWG
vpn-awg-add-btn = Добавить устройство
vpn-awg-get-config-btn = Получить конфиг
vpn-awg-rename-btn = Переименовать
vpn-awg-delete-btn = Удалить
vpn-awg-delete-yes-btn = Да, удалить
vpn-awg-restore-btn = Включить ключи
vpn-awg-show-qr-btn = Показать QR-код
vpn-awg-show-file-btn = Показать файл
vpn-awg-done-btn = Готово

# Клиенты AmneziaWG: нужна версия с поддержкой AWG 3.1 (Android 3.1.20260814+, iOS с «AWG 3.1 support»)
vpn-awg-android-btn = Android (Google Play)
vpn-awg-android-url = https://play.google.com/store/apps/details?id=org.amnezia.awg
vpn-awg-apk-btn = Android (APK без Google Play)
vpn-awg-apk-url = https://github.com/amnezia-vpn/amneziawg-android/releases/latest
vpn-awg-ios-btn = iPhone и iPad (App Store)
vpn-awg-ios-url = https://apps.apple.com/app/amneziawg/id6478942365

# Уведомления и ошибки
vpn-awg-deleted-alert = Устройство удалено
vpn-awg-restored-alert = Ключи включены
vpn-awg-limit-alert = Лимит устройств исчерпан ({ $used } из { $limit }). Удалите ненужное или напишите VP4HR.
vpn-awg-denied-alert = AmneziaWG доступен только активным мемберам LBG. Если доступ закрыт по ошибке, напишите VP4HR.
vpn-awg-error-alert = Панель VPN недоступна. Попробуйте позже или напишите VP4HR.
