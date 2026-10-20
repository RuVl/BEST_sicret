"""Схемы обмена с веб-панелью AmneziaWG (amneziawg-web).

Поля повторяют ``PeerSummaryDto`` из ``GET /api/peers``. Конверта, как у 3x-ui, нет:
успех - JSON как есть, ошибка - ``{"error": "..."}`` с HTTP-статусом.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AwgPeer(BaseModel):
    """Пир AmneziaWG, как его видит панель."""

    model_config = ConfigDict(extra="ignore")

    # Числовой ID строки в БД панели - нужен для config/patch/remove.
    id: int
    name: str = ""
    # Имя клиента установщика: суффикс файла ``awg0-client-<name>.conf``.
    friendly_name: str | None = None
    comment: str | None = None
    has_config: bool = False
    # online / inactive / never / disabled
    connection_status: str = ""
    # Счётчики интерфейса со стороны сервера: rx - получено от клиента, tx - отправлено ему.
    rx_bytes: int = 0
    tx_bytes: int = 0
    latest_handshake_at: datetime | None = None

    @property
    def disabled(self) -> bool:
        return self.connection_status == "disabled"


class AwgUsagePeriod(BaseModel):
    """Трафик за период. Панель сериализует байты строками - pydantic приводит их к int."""

    model_config = ConfigDict(extra="ignore")

    rx_bytes: int = 0
    tx_bytes: int = 0


class AwgUsageSummary(BaseModel):
    """``GET /api/peers/:id/usage/summary``: трафик за сутки, неделю и 30 дней по снимкам поллера."""

    model_config = ConfigDict(extra="ignore")

    day: AwgUsagePeriod = AwgUsagePeriod()
    week: AwgUsagePeriod = AwgUsagePeriod()
    month: AwgUsagePeriod = AwgUsagePeriod()
