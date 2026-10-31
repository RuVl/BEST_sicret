"""Клиентский ``.conf`` AmneziaWG.

API 3x-ui конфиг не отдаёт - его собирает веб-интерфейс панели (``amneziawgConfig.ts``),
поэтому бот повторяет ту же сборку: ключи и адрес устройства плюс параметры сервера, которые
обязаны совпасть один в один, иначе handshake молча не проходит.
"""

from includes.awg.exceptions import AwgError
from includes.awg.schemas import AwgInbound, AwgPeer

# Как ``effectiveMtu`` панели: мусор S4 дописывается к каждому пакету и не урезается под MTU,
# поэтому без явного MTU туннель уменьшаем на S4, но не ниже минимума IPv6.
_DEFAULT_MTU = 1420
_MIN_MTU = 1280


def effective_mtu(configured: int, s4: int | None) -> int:
    if configured > 0:
        return configured
    return max(_DEFAULT_MTU - max(s4 or 0, 0), _MIN_MTU)


def build_client_config(peer: AwgPeer, inbound: AwgInbound, endpoint_host: str, remark: str = "") -> str:
    """Текст ``.conf`` устройства. Внутри приватный ключ - не логировать и не хранить."""
    if not peer.private_key or not peer.address:
        raise AwgError(f"У клиента {peer.email} в панели нет ключа или адреса")
    if not inbound.server.public_key:
        raise AwgError(f"У инбаунда {inbound.id} нет публичного ключа сервера")

    server = inbound.server
    lines = ["[Interface]", f"PrivateKey = {peer.private_key}", f"Address = {peer.address}"]
    dns = [value for value in (server.primary_dns, server.secondary_dns) if value.strip()]
    if dns:
        lines.append(f"DNS = {', '.join(dns)}")
    lines.append(f"MTU = {effective_mtu(server.mtu, server.s4)}")

    # Запасные значения - те же, что подставляет панель, когда поле пустое.
    lines += [
        f"Jc = {server.jc if server.jc is not None else 5}",
        f"Jmin = {server.jmin if server.jmin is not None else 10}",
        f"Jmax = {server.jmax if server.jmax is not None else 50}",
        f"S1 = {server.s1 if server.s1 is not None else 30}",
        f"S2 = {server.s2 if server.s2 is not None else 45}",
    ]
    if server.s3:
        lines.append(f"S3 = {server.s3}")
    if server.s4:
        lines.append(f"S4 = {server.s4}")
    # Пустой H - классический тип сообщения WireGuard (1-4), как в движке панели.
    for number, value in enumerate((server.h1, server.h2, server.h3, server.h4), start=1):
        lines.append(f"H{number} = {value.strip() or number}")
    for key, value in (("I1", server.i1), ("I2", server.i2), ("I3", server.i3), ("I4", server.i4), ("I5", server.i5)):
        if value:
            lines.append(f"{key} = {value}")

    for key, value in (
        ("HeaderProtectionKey", server.header_protection_key),
        ("ContentPaddingAddition", server.content_padding_addition),
        ("RekeyAfterTime", server.rekey_after_time),
        ("RekeyTimeout", server.rekey_timeout),
        ("RejectAfterTime", server.reject_after_time),
        ("KeepaliveTimeout", server.keepalive_timeout),
        ("MaxHandshakeAttempts", server.max_handshake_attempts),
    ):
        if value.strip():
            lines.append(f"{key} = {value}")
    if server.random_trailers:
        lines.append("RandomTrailers = on")
    if server.disable_cookies:
        lines.append("DisableCookies = on")

    lines.append("")
    if remark:
        lines.append(f"# {remark}")
    lines += ["[Peer]", f"PublicKey = {server.public_key}"]
    if peer.preshared_key:
        lines.append(f"PresharedKey = {peer.preshared_key}")
    lines += ["AllowedIPs = 0.0.0.0/0, ::/0", f"Endpoint = {endpoint_host}:{inbound.port}"]
    if peer.keep_alive:
        lines.append(f"PersistentKeepalive = {peer.keep_alive}")

    # Перевод строки внутри значения открыл бы новую секцию, а PostUp из неё wg-quick выполнит от root.
    if any(char < " " or char == "\x7f" for line in lines for char in line):
        raise AwgError(f"Параметры инбаунда {inbound.id} или клиента {peer.email} содержат управляющие символы")
    return "\n".join(lines) + "\n"
