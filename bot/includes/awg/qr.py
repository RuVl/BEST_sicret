"""QR-код конфига: приложение AmneziaWG на телефоне сканирует его с экрана компьютера."""

import io

import segno


def render_config_qr(config: str) -> bytes:
    """PNG с QR-кодом текста конфига (уровень коррекции L - конфиг AWG 2.0 длинный)."""
    buffer = io.BytesIO()
    segno.make(config, error="l", micro=False).save(buffer, kind="png", scale=6, border=4)
    return buffer.getvalue()
