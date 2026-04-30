# Text (md2)
refund-bill-view = \- \* Чек: `{ $bill_filename }`
refund-add-bill = Отправьте чек \(в формате документа, до 5 МБ\)
refund-apply-was-sent = Заявка на рефанд была отправлена казначею
treasure-refund-apply = Поступила заявка на рефанд:
    от: @{ $username }
    причина: `{ $reason }`
    сумма: `{ $total_price }`
    реквизиты: `{ $requisites }`
    чек: `{ $bill_filename }`

# Buttons
refund-add-bill-btn = Прикрепить чек
refund-send-btn = Отправить рефанд

# Errors
refund-schema-not-found = Схема создания заявки не найдена\!
    Попробуйте начать заново или обратитесь в поддержку
refund-bill-too-big = Размер файла не должен превышать *5 МБ*\!
