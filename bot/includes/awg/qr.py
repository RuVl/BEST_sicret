"""QR-код конфига: приложение на телефоне сканирует его с экрана компьютера."""

import io
from collections.abc import Callable
from dataclasses import dataclass

import segno
from segno import DataOverflowError


def render_config_qr(config: str) -> bytes:
    """PNG с QR-кодом текста конфига (уровень коррекции L - конфиг AWG 2.0 длинный)."""
    return _png(segno.make(config, error="l", micro=False))


def _png(code: segno.QRCode) -> bytes:
    buffer = io.BytesIO()
    code.save(buffer, kind="png", scale=6, border=4)
    return buffer.getvalue()


def _encode(config: str) -> segno.QRCode | None:
    try:
        return segno.make(config, error="l", micro=False)
    except DataOverflowError:
        return None


@dataclass(frozen=True)
class FittedQr:
    png: bytes
    # Сколько первых исключений вошло в QR (из ``total``): остальные есть только в файле.
    included: int
    total: int

    @property
    def truncated(self) -> bool:
        return self.included < self.total


def fit_config_qr(build: Callable[[int], str], total: int) -> FittedQr | None:
    """QR конфига с наибольшим началом списка исключений, которое в него влезает.

    ``build(n)`` - текст конфига с первыми ``n`` исключениями; порядок списка и есть приоритет.
    Размер QR зависит от режима кодирования, поэтому подбираем реальным кодированием (двоичный
    поиск, ~8 попыток на 255 приложений), а не оценкой байтов. ``None`` - не влезает даже без исключений.
    """
    best = _encode(build(total))
    if best is not None:
        return FittedQr(_png(best), total, total)

    low, high = 0, total - 1  # total уже не влез
    best_n = -1
    while low <= high:
        middle = (low + high) // 2
        code = _encode(build(middle))
        if code is None:
            high = middle - 1
        else:
            best, best_n = code, middle
            low = middle + 1
    if best is None:
        return None
    return FittedQr(_png(best), best_n, total)
