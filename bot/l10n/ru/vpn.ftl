# Remember to escape some characters for MarkdownV2 syntax:
# https://core.telegram.org/bots/api#markdownv2-style
# Пустая строка обрывает сообщение, поэтому пустые абзацы — через { "" }.

vpn-none = *VPN\-подписка*
    { "" }
    Подписки пока нет\. Нажмите «Выпустить» — бот создаст ключ и пришлёт ссылку\.

vpn-active = *VPN\-подписка активна*
    { "" }
    Ссылка\-подписка \(нажмите, чтобы скопировать\):
    `{ $url }`
    { "" }
    Трафик за текущий период: { $traffic }

vpn-orphaned = *VPN\-подписка недействительна*
    { "" }
    Ключ удалён из панели, старая ссылка больше не работает\.
    Нажмите «Выпустить» — бот создаст новый ключ и пришлёт новую ссылку\.

vpn-disabled = *VPN\-подписка отключена*
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
vpn-access-denied-alert = Доступ к VPN только для активных мемберов LBG

# === AmneziaWG (запасной протокол по разрешению админа) ===
# Один конфиг - одно устройство, поэтому ключи заводятся по устройствам.

vpn-awg-hint = *AmneziaWG*
    Вам открыт запасной протокол\. Если VLESS не подключается, откройте «AmneziaWG» и добавьте устройство — бот пришлёт файл и QR\-код\.

vpn-awg-devices = *AmneziaWG*
    { "" }
    Один конфиг — одно устройство: на двух устройствах сразу он работать не будет\. Для телефона и ноутбука добавьте два устройства\.
    { "" }
    Устройств: { $used } из { $limit }
    { $devices }

vpn-awg-device-card = *{ $name }*
    { "" }
    Статус: { $status }
    Последнее подключение: { $handshake }
    { "" }
    { "*" }Трафик* \(скачано / отправлено\)
    За сутки: { $day }
    За 7 дней: { $week }
    За 30 дней: { $month }

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
vpn-awg-panel-error-hint = Панель AmneziaWG сейчас недоступна, статус и трафик не показаны\.

vpn-awg-delete-confirm = *Удалить «{ $name }»?*
    { "" }
    Его конфиг перестанет работать\. Новый можно получить, добавив устройство заново\.

vpn-awg-granted-notice = *Вам открыт AmneziaWG*
    { "" }
    Это запасной VPN\-протокол на случай, если VLESS не подключается\.
    Откройте /start → «VPN\-подписка» → «AmneziaWG» и добавьте устройство\. Один конфиг — одно устройство, всего можно завести { $limit }\.

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
vpn-awg-status-missing-part = ключа нет в панели, получите конфиг заново
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

# Уведомления и ошибки
vpn-awg-deleted-alert = Устройство удалено
vpn-awg-restored-alert = Ключи включены
vpn-awg-limit-alert = Лимит устройств исчерпан ({ $used } из { $limit }). Удалите ненужное или напишите VP4HR.
vpn-awg-denied-alert = AmneziaWG вам не выдан. Если он нужен, напишите VP4HR.
vpn-awg-error-alert = Панель AmneziaWG недоступна. Попробуйте позже или напишите VP4HR.
