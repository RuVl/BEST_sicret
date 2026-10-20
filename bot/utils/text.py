def truncate(text: str, max_len: int = 15) -> str:
    """Обрезает текст до max_len символов с добавлением '…'"""
    return text[:max_len] + "…" if len(text) > max_len else text


def format_traffic(used_bytes: int) -> str:
    """Байты в читаемый вид: до гигабайта - мегабайты, дальше гигабайты."""
    _GB = 1024**3
    if used_bytes < _GB:
        return f"{used_bytes / 1024**2:.1f} МБ"
    return f"{used_bytes / _GB:.2f} ГБ"
