# Remember to escape some characters for MarkdownV2 syntax:
# https://core.telegram.org/bots/api#markdownv2-style

start-msg = Добро пожаловать в BEST sicret\! Чтобы выбрать действие используйте команды\.

# actions
back = Назад
delete = Удалить
add-item = Добавить элемент

# Errors
invalid-stack = Внутренняя ошибка (забыли вас)

# --- Refund Dialog ---
refund_summary = Заявка на рефанд\n\
Мероприятие: { $event }\n\
Причина: { $reason }\n\
Сумма: { $amount }\n\
Реквизиты: { $requisites }\n\
Фото чека: { $receipt_photo }

refund_edit_event = Введите название мероприятия:
refund_edit_reason = Введите причину возврата:
refund_edit_amount = Введите сумму (руб, например 1234.56):
refund_edit_requisites = Введите реквизиты (СБП, карта и т.п.):
refund_edit_receipt = Введите путь к фото чека или загрузите файл:
refund_send = Отправить заявку
refund_cancel = Отмена
refund_back = Назад