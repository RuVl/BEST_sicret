"""Схемы AmneziaWG-инбаунда панели 3x-ui (v3.11+).

Поля повторяют Go-структуры панели: ``amneziawg.InboundSettings.Server`` (параметры сервера и
обфускации, общие для всех клиентов) и ``model.ClientRecord`` (ключи и адрес устройства).
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from includes.vpn.schemas import ClientTraffic

# 3x-ui отмечает клиента онлайн по трафику, а keepalive у нас 25 с - три минуты тишины значат «не в сети».
ONLINE_WINDOW = timedelta(minutes=3)
DEFAULT_KEEPALIVE = 25

ConnectionStatus = Literal["online", "inactive", "never", "disabled"]


class AwgServer(BaseModel):
    """Блок ``settings.server`` инбаунда: всё, что клиентский конфиг должен повторить один в один."""

    # H1-H4 панель хранит строками, но может прислать и числом - приводим к строке.
    model_config = ConfigDict(populate_by_name=True, extra="ignore", coerce_numbers_to_str=True)

    public_key: str = Field("", alias="publicKey")
    primary_dns: str = Field("", alias="primaryDns")
    secondary_dns: str = Field("", alias="secondaryDns")
    mtu: int = 0

    jc: int | None = None
    jmin: int | None = None
    jmax: int | None = None
    s1: int | None = None
    s2: int | None = None
    s3: int | None = None
    s4: int | None = None
    h1: str = ""
    h2: str = ""
    h3: str = ""
    h4: str = ""
    i1: str = ""
    i2: str = ""
    i3: str = ""
    i4: str = ""
    i5: str = ""

    # AWG 3.0 / 3.1: без 3.1-клиента с этими полями handshake молча не пройдёт.
    header_protection_key: str = Field("", alias="headerProtectionKey")
    content_padding_addition: str = Field("", alias="contentPaddingAddition")
    rekey_after_time: str = Field("", alias="rekeyAfterTime")
    rekey_timeout: str = Field("", alias="rekeyTimeout")
    reject_after_time: str = Field("", alias="rejectAfterTime")
    keepalive_timeout: str = Field("", alias="keepaliveTimeout")
    max_handshake_attempts: str = Field("", alias="maxHandshakeAttempts")
    random_trailers: bool = Field(False, alias="randomTrailers")
    disable_cookies: bool = Field(False, alias="disableCookies")


class AwgInbound(BaseModel):
    """AmneziaWG-инбаунд из ``GET /panel/api/inbounds/get/:id``."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    protocol: str = ""
    remark: str = ""
    listen: str = ""
    port: int
    server: AwgServer

    @classmethod
    def from_panel(cls, obj: dict[str, Any]) -> "AwgInbound":
        """``settings`` панель отдаёт JSON-строкой - разбираем и достаём ``server``."""
        settings = obj.get("settings") or {}
        if isinstance(settings, str):
            settings = json.loads(settings) if settings else {}
        return cls.model_validate({**obj, "server": settings.get("server") or {}})


class AwgPeer(BaseModel):
    """Клиент панели в AmneziaWG-инбаунде - одно устройство: ключи, адрес и счётчики трафика."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    email: str
    enable: bool = True
    private_key: str = Field("", alias="privateKey")
    public_key: str = Field("", alias="publicKey")
    preshared_key: str = Field("", alias="preSharedKey")
    # Адрес устройства в туннеле (``10.70.0.2/32``); несколько адресов - через запятую.
    address: str = ""
    keep_alive: str = Field("", alias="keepAlive")
    # Счётчики 3x-ui глазами клиента: up - отправлено устройством, down - скачано им.
    up: int = 0
    down: int = 0
    last_online_at: datetime | None = None

    @field_validator("keep_alive", mode="before")
    @classmethod
    def keep_alive_to_str(cls, value: Any) -> str:
        # Число (25) или диапазон AWG 3.x (``20-30``); 0 - keepalive выключен.
        if value in (None, 0, "0"):
            return ""
        return str(value)

    @property
    def disabled(self) -> bool:
        return not self.enable

    def connection_status(self, now: datetime | None = None) -> ConnectionStatus:
        if not self.enable:
            return "disabled"
        if self.last_online_at is None:
            return "never"
        if (now or datetime.now(UTC)) - self.last_online_at <= ONLINE_WINDOW:
            return "online"
        return "inactive"

    @classmethod
    def from_panel(cls, obj: dict[str, Any], inbound_id: int, traffic: ClientTraffic | None) -> "AwgPeer":
        """Собрать устройство из ``/clients/get/:email`` и счётчиков ``/clients/traffic/:email``.

        ``client.allowedIPs`` у панели одна колонка на все туннельные инбаунды, поэтому адрес
        именно этого инбаунда берём из ``tunnelAllowedIPs``, а общий - только запасным.
        """
        client = obj["client"]
        tunnel = (obj.get("tunnelAllowedIPs") or {}).get(str(inbound_id))
        address = tunnel if tunnel is not None else client.get("allowedIPs")
        if isinstance(address, list):
            address = ", ".join(address)

        last_online = None
        if traffic is not None and traffic.last_online > 0:
            last_online = datetime.fromtimestamp(traffic.last_online / 1000, UTC)
        return cls.model_validate(
            {
                **client,
                "address": address or "",
                "up": traffic.up if traffic else 0,
                "down": traffic.down if traffic else 0,
                "last_online_at": last_online,
            }
        )


class AwgClientPayload(BaseModel):
    """Тело нового устройства для ``POST /panel/api/clients/add``.

    Ключей и адреса нет намеренно: панель генерирует пару ключей и выдаёт свободный адрес
    из подсети инбаунда сама. Повторный вызов с тем же email ключи не перевыпускает.
    """

    model_config = ConfigDict(populate_by_name=True)

    email: str
    sub_id: str = Field(alias="subId")
    enable: bool = True
    tg_id: int = Field(0, alias="tgId")
    comment: str = ""
    group: str = ""
    keep_alive: int = Field(DEFAULT_KEEPALIVE, alias="keepAlive")
    # Лимиты VLESS устройству не нужны: один ключ и так работает только на одном устройстве.
    limit_ip: int = Field(0, alias="limitIp")
    total_bytes: int = Field(0, alias="totalGB")
    expiry_time: int = Field(0, alias="expiryTime")
    reset: int = 0
