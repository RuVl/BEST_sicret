import re


def escape_mdv2(text) -> str | None:
    """Экранировать текст для MarkdownV2 (``None`` остаётся ``None``).

    Обратный слэш - тоже: иначе ``PC\\-1`` превратился бы в экранированный слэш и голый ``-``,
    и Telegram отверг бы всё сообщение.
    """
    return re.sub(r"([\\_*\[\]()~`>#+\-=|{}.!])", r"\\\1", str(text)) if text is not None else None
