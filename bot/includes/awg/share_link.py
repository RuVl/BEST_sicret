"""Клиентский ``.conf`` AmneziaWG из ссылок, которые отдаёт панель.

Конфиг собирает сама 3x-ui: ``GET /panel/api/clients/links/:email`` возвращает ссылки клиента
во всех его инбаундах, а AmneziaWG среди них - ``vpn://<base64url текста .conf>`` (так же он
попадает в подписку). Бот только находит ссылку нужного устройства и раскрывает её, поэтому
параметры обфускации всегда совпадают с сервером и новые поля AWG не требуют правок бота.
"""

import base64
import binascii
from ipaddress import ip_address

from includes.awg.exceptions import AwgError
from includes.awg.schemas import AwgPeer

_SCHEME = "vpn://"


def _decode(link: str) -> str | None:
    payload = link.removeprefix(_SCHEME)
    try:
        # base64url без паддинга - дописываем его, иначе b64decode откажется.
        return base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()
    except (binascii.Error, ValueError):
        return None


def _first_address(value: str | None) -> str:
    # С IPv6 адресов несколько, через запятую; устройство однозначно определяет первый (IPv4).
    return (value or "").split(",")[0].strip()


def _value(lines: list[str], key: str) -> str | None:
    prefix = f"{key} = "
    return next((line.removeprefix(prefix) for line in lines if line.startswith(prefix)), None)


def _check_endpoint(endpoint: str | None, email: str) -> None:
    """Endpoint должен вести на сервер снаружи. Без Listen IP / Share address инбаунда панель
    подставляет адрес, по которому к ней пришёл запрос, - для бота это внутренний адрес."""
    host = (endpoint or "").rpartition(":")[0].strip("[]")
    if not host or host == "localhost":
        raise AwgError(f"В конфиге {email} нет адреса сервера: задайте Listen IP или Share address инбаунда")
    try:
        address = ip_address(host)
    except ValueError:
        # Домен пропускаем: проксирует ли его Cloudflare (UDP тогда не дойдёт), отсюда не понять.
        return
    if address.is_loopback or address.is_unspecified or address.is_private:
        raise AwgError(f"В конфиге {email} внутренний адрес сервера {host}: задайте Listen IP инбаунда")


def extract_device_config(links: list[str], peer: AwgPeer) -> str:
    """Текст ``.conf`` устройства из ссылок клиента. Внутри приватный ключ - не логировать и не хранить.

    У клиента могут быть ссылки других протоколов и других AmneziaWG-инбаундов - берём ту,
    в которой ключ и адрес этого устройства.
    """
    if not peer.private_key:
        raise AwgError(f"У клиента {peer.email} в панели нет ключа")

    for link in links:
        if not link.startswith(_SCHEME):
            continue
        text = _decode(link)
        if text is None:
            continue
        lines = text.splitlines()
        if "[Interface]" not in lines or "[Peer]" not in lines:
            continue
        if _value(lines, "PrivateKey") != peer.private_key:
            continue
        if _first_address(_value(lines, "Address")) != _first_address(peer.address):
            continue
        _check_endpoint(_value(lines, "Endpoint"), peer.email)
        return text if text.endswith("\n") else text + "\n"

    raise AwgError(f"Панель не отдала конфиг AmneziaWG для {peer.email}")
