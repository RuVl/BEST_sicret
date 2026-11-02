def truncate(text: str, max_len: int = 15) -> str:
    """Обрезает текст до max_len символов с добавлением '…'"""
    return text[:max_len] + "…" if len(text) > max_len else text


def format_traffic(used_bytes: int) -> str:
    """Байты в читаемый вид: до гигабайта - мегабайты, дальше гигабайты."""
    _GB = 1024**3
    if used_bytes < _GB:
        return f"{used_bytes / 1024**2:.1f} МБ"
    return f"{used_bytes / _GB:.2f} ГБ"


# Предел длины текста одного сообщения Telegram.
TELEGRAM_MESSAGE_LIMIT = 4096


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Разбить текст на сообщения не длиннее ``limit`` - по строкам, чтобы не рвать разметку.

    Строку длиннее предела режем по символам, но не после ``\\``: иначе экранирование MarkdownV2
    осталось бы без пары, и Telegram отверг бы оба куска.
    """
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            cut = limit
            while cut > 1 and line[cut - 1] == "\\":
                cut -= 1
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:cut])
            line = line[cut:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            candidate = line
        current = candidate
    if current:
        chunks.append(current)
    return chunks
