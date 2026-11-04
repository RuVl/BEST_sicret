# Локализация (Fluent)

Все тексты бота лежат в `l10n/<язык>/*.ftl` (сейчас только `ru`), файлы подхватываются автоматически. Один файл - одна
фича. Правила суффиксов ключей, экранирования и ловушки синтаксиса - в [CLEAN_CODE.md](../../CLEAN_CODE.md), раздел 5.

```fluent
auth-attempts-left =
    У вас осталось { $count } { $count ->
        [one] попытка
        [few] попытки
       *[many] попыток
    } до блокировки
```

```python
l10n.format_value("auth-attempts-left", args={"count": 2})
```

`{ $count }` подставляет переменную, `->` выбирает вариант, `*` отмечает вариант по умолчанию.

Документация: [синтаксис](https://projectfluent.org/fluent/guide/), [песочница](https://projectfluent.org/play/).
