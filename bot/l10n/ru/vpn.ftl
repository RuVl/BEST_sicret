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

# AmneziaWG (запасной протокол по разрешению админа)
vpn-awg-hint = *AmneziaWG*
    Вам открыт запасной протокол\. Если VLESS не подключается, нажмите «Конфиг AmneziaWG» — бот пришлёт файл и QR\-код для приложения AmneziaWG\.

vpn-awg-config-caption = Конфиг AmneziaWG\. Импортируйте файл в приложение AmneziaWG или AmneziaVPN\.
    { "" }
    Это ваш личный ключ — никому его не пересылайте\.

vpn-awg-qr-caption = Тот же конфиг QR\-кодом: отсканируйте его приложением AmneziaWG на телефоне\.

vpn-awg-granted-notice = *Вам открыт AmneziaWG*
    { "" }
    Это запасной VPN\-протокол на случай, если VLESS не подключается\.
    Откройте /start → «VPN\-подписка» → «Конфиг AmneziaWG»\.

vpn-awg-suspended-notice = Ваш ключ AmneziaWG отключён: вы больше не активный мембер LBG\.
    { "" }
    Если это ошибка — напишите VP4HR\.

vpn-awg-suspend-report = *Автоотключение ключей AmneziaWG*
    { "" }
    Отключено: { $revoked }
    Ошибок: { $failed }
    { "" }
    { $details }

# Buttons
vpn-awg-btn = Конфиг AmneziaWG
vpn-issue-btn = Выпустить
vpn-refresh-btn = Обновить
vpn-handbook-btn = Как подключиться
vpn-handbook-url = https://docs.google.com/document/d/1gcmkXYgEY308JLwmrzNfeBirzJZDPrPx/edit

# Notifications and errors
vpn-issued = Подписка выпущена
vpn-error = Панель VPN недоступна. Попробуйте позже или напишите VP4HR.
vpn-access-denied = Доступ к VPN только для активных мемберов LBG
vpn-awg-sent = Конфиг отправлен
vpn-awg-denied = AmneziaWG вам не выдан. Если он нужен, напишите VP4HR.
vpn-awg-error = Панель AmneziaWG недоступна. Попробуйте позже или напишите VP4HR.
