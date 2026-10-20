"""Схемы обмена с веб-панелью AmneziaWG (amneziawg-web).

Поля повторяют ``PeerSummaryDto`` из ``GET /api/peers``. Конверта, как у 3x-ui, нет:
успех - JSON как есть, ошибка - ``{"error": "..."}`` с HTTP-статусом.
"""

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
    rx_bytes: int = 0
    tx_bytes: int = 0

    @property
    def disabled(self) -> bool:
        return self.connection_status == "disabled"
