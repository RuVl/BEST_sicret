"""Схемы клиента AmneziaWG-инбаунда панели 3x-ui (v3.11+).

Поля повторяют Go-структуру панели ``model.ClientRecord``: ключи и адрес устройства.
Параметры сервера и обфускации бот не читает - готовый конфиг собирает сама панель.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from includes.vpn.schemas import ClientDetails, ClientTraffic

# 3x-ui отмечает клиента онлайн по трафику, а keepalive у нас 25 с - три минуты тишины значат «не в сети».
ONLINE_WINDOW = timedelta(minutes=3)
DEFAULT_KEEPALIVE = 25

ConnectionStatus = Literal["online", "inactive", "never", "disabled"]


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
    def from_panel(cls, details: ClientDetails, inbound_id: int, traffic: ClientTraffic | None) -> "AwgPeer":
        """Собрать устройство из ``/clients/get/:email`` и счётчиков ``/clients/traffic/:email``.

        ``client.allowedIPs`` у панели одна колонка на все туннельные инбаунды, поэтому адрес
        именно этого инбаунда берём из ``tunnelAllowedIPs``, а общий - только запасным.
        """
        client = details.client
        tunnel = details.tunnel_allowed_ips.get(str(inbound_id))
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
