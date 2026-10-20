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
vpn-issued = Подписка выпущена
vpn-error = Панель VPN недоступна. Попробуйте позже или напишите VP4HR.
vpn-access-denied = Доступ к VPN только для активных мемберов LBG

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

vpn-awg-suspended-hint = Ключи выключены, пока вы не состояли в LBG\. Нажмите «Включить ключи»\.
vpn-awg-panel-error-hint = Панель AmneziaWG сейчас недоступна, статус устройств не показан\.

vpn-awg-delete-confirm = *Удалить устройство { $number }?*
    { "" }
    Его конфиг перестанет работать\. Новый можно получить, добавив устройство заново\.

vpn-awg-config-caption = Конфиг AmneziaWG для устройства { $number }\. Импортируйте файл в приложение AmneziaWG или AmneziaVPN\.
    { "" }
    Один конфиг — одно устройство\. Это ваш личный ключ — никому его не пересылайте\.

vpn-awg-qr-caption = Тот же конфиг QR\-кодом: отсканируйте его приложением AmneziaWG на телефоне\.

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

# Строки списка устройств - обычный текст, экранирует код
vpn-awg-device-line = Устройство { $number }: { $status }
vpn-awg-devices-empty = Устройств пока нет. Нажмите «Добавить устройство».
vpn-awg-status-online = в сети
vpn-awg-status-inactive = давно не подключалось
vpn-awg-status-never = ещё не подключалось
vpn-awg-status-disabled = выключено
vpn-awg-status-missing = ключа нет в панели, запросите конфиг
vpn-awg-status-unknown = статус неизвестен

# Кнопки
vpn-awg-btn = AmneziaWG
vpn-awg-add-btn = Добавить устройство
vpn-awg-config-btn = Конфиг { $number }
vpn-awg-delete-btn = Удалить { $number }
vpn-awg-delete-yes-btn = Да, удалить
vpn-awg-restore-btn = Включить ключи

# Уведомления и ошибки
vpn-awg-sent = Конфиг отправлен
vpn-awg-deleted = Устройство удалено
vpn-awg-restored = Ключи включены
vpn-awg-limit = Лимит устройств исчерпан ({ $used } из { $limit }). Удалите ненужное или напишите VP4HR.
vpn-awg-denied = AmneziaWG вам не выдан. Если он нужен, напишите VP4HR.
vpn-awg-error = Панель AmneziaWG недоступна. Попробуйте позже или напишите VP4HR.
