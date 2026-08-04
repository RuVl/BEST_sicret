# Remember to escape some characters for MarkdownV2 syntax:
# https://core.telegram.org/bots/api#markdownv2-style
# Пустая строка обрывает сообщение, поэтому пустые абзацы — через { "" }.
# Строку нельзя начинать с `*` (это синтаксис вариантов Fluent) — оборачиваем в { "*…*" }.

profile-card = *{ $name }*
    { "" }
    Статус: { $category }
    { "" }
    { "*Роли:*" } { $roles }
    { "" }
    { "*Локальная вовлечённость:*" } { $local_involvement }
    { "*Международная вовлечённость:*" } { $international_involvement }
    { "*Мероприятия BEST:*" } { $best_events }

profile-active = активный мембер
profile-inactive = неактивен

profile-not-member = Привет, { $name }\!
    { "" }
    Тебя пока нет в базе участников BEST SPb\. Этот бот — для мемберов локальной группы\.
    { "" }
    Хочешь к нам? Набор идёт осенью и весной:
    • [сайт](https://best-spbpu.ru/)
    • [ВКонтакте](https://vk.ru/siospbstu)
    { "" }
    Если ты уже мембер — проверь, что в таблице участников указан твой Telegram\-username, и нажми /start

# Buttons
profile-vpn-btn = VPN-подписка
close = Закрыть
