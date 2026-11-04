"""Схемы клиента AmneziaWG-инбаунда панели 3x-ui (v3.11+).

Поля повторяют Go-структуру панели ``model.ClientRecord``: ключи и адрес устройства.
Параметры сервера и обфускации бот не читает - готовый конфиг собирает сама панель.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from py3xui import ClientDetails, ClientTraffic
from pydantic import BaseModel, ConfigDict, Field, field_validator

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
        tunnel = details.tunnel_allowed_ips.get(inbound_id)
        address = tunnel if tunnel is not None else ", ".join(client.allowed_ips)

        last_online = None
        if traffic is not None and traffic.last_online > 0:
            last_online = datetime.fromtimestamp(traffic.last_online / 1000, UTC)
        return cls(
            email=client.email,
            enable=client.enable,
            private_key=client.private_key,
            public_key=client.public_key,
            preshared_key=client.pre_shared_key,
            keep_alive=client.keep_alive,
            address=address,
            up=traffic.up if traffic else 0,
            down=traffic.down if traffic else 0,
            last_online_at=last_online,
        )
