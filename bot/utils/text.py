def truncate(text: str, max_len: int = 15) -> str:
    """Обрезает текст до max_len символов с добавлением '…'"""
    return text[:max_len] + '…' if len(text) > max_len else text