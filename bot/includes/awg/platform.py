"""Платформа устройства и то, что от неё зависит в клиентском ``.conf``.

``ExcludedApplications`` (приложения мимо VPN) понимают только Android-клиенты - AmneziaWG
для Android и WG Tunnel. AmneziaWG для iOS/macOS и Windows отвергают конфиг с незнакомым ключом
целиком, а ``awg-quick`` на Linux падает на нём в ``awg setconf``. Поэтому список попадает только
в конфиг устройства, про которое человек сказал, что это Android.

``# Name = ...`` - комментарий: все клиенты его пропускают, а WG Tunnel берёт из него имя туннеля,
если это первая строка файла.
"""

import re
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Literal, get_args

import structlog
from structlog.typing import FilteringBoundLogger

logger: FilteringBoundLogger = structlog.get_logger("awg")

DevicePlatform = Literal["android", "ios", "windows", "macos", "linux"]
PLATFORMS: tuple[DevicePlatform, ...] = get_args(DevicePlatform)

# Российские приложения, которые на Android идут мимо VPN: правится без кода, по пакету в строке.
# Лежит рядом с кодом: это часть логики выдачи конфига, а не данные, которые бот пишет сам.
EXCLUDED_APPS_FILE = Path(__file__).with_name("excluded_apps.txt")

_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+")


def is_platform(value: str | None) -> bool:
    return value in PLATFORMS


def parse_excluded_apps(text: str) -> tuple[str, ...]:
    """Пакеты из файла: пустые строки и ``#``-комментарии пропускаем, дубли убираем, порядок храним."""
    packages: dict[str, None] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if not _PACKAGE.fullmatch(line):
            # Кривая строка в конфиге сломала бы его импорт на телефоне - такой файл не берём совсем.
            raise ValueError(f"{EXCLUDED_APPS_FILE.name}: не похоже на пакет Android: {line!r}")
        packages[line] = None
    return tuple(packages)


@lru_cache(maxsize=1)
def excluded_apps() -> tuple[str, ...]:
    """Список для Android-конфигов. Нет файла или он битый - конфиг выдаётся без исключений:
    VPN работает, просто российские приложения тоже идут через него. Ошибку видно в логе при старте."""
    try:
        return parse_excluded_apps(EXCLUDED_APPS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("awg-excluded-apps-unavailable", path=str(EXCLUDED_APPS_FILE), error=str(exc))
        return ()


def _interface_end(lines: list[str]) -> int:
    """Индекс, куда дописывать ключ ``[Interface]``: перед пустыми строками и комментариями над ``[Peer]``."""
    end = next((i for i, line in enumerate(lines) if line.startswith("[") and i > 0), len(lines))
    while end > 0 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return end


def personalize_config(
    conf: str,
    platform: DevicePlatform | None,
    *,
    name: str,
    excluded: Sequence[str] = (),
) -> str:
    """Конфиг панели под устройство: имя туннеля первой строкой и, для Android, приложения мимо VPN."""
    lines = conf.splitlines()
    if platform == "android" and excluded:
        lines.insert(_interface_end(lines), f"ExcludedApplications = {','.join(excluded)}")
    if name:
        lines.insert(0, f"# Name = {name}")
    return "\n".join(lines) + "\n"
