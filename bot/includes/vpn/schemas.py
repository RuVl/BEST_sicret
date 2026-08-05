"""Схемы обмена с панелью 3x-ui (v3).

Поля повторяют Go-структуры панели: ``model.Client`` и ``xray.ClientTraffic``.
Панель отдаёт всё в конверте ``{success, msg, obj}`` - его разбирает ``client.py``.
"""

from pydantic import BaseModel, ConfigDict, Field

# XTLS-Vision - единственный flow, который мы выдаём: панель на update перезаписывает поле
# тем, что пришло в теле, поэтому пустой flow молча снёс бы настройку клиента.
DEFAULT_FLOW = "xtls-rprx-vision"


class XuiClientPayload(BaseModel):
    """Тело клиента для ``POST /panel/api/clients/add`` и ``/update/:email``."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="UUID клиента")
    email: str
    sub_id: str = Field(alias="subId")
    flow: str = DEFAULT_FLOW
    enable: bool = True
    tg_id: int = Field(0, alias="tgId")
    comment: str = ""
    group: str = ""
    limit_ip: int = Field(0, alias="limitIp")
    # Вопреки имени, панель хранит в totalGB именно БАЙТЫ (в её примерах 53687091200 = 50 ГиБ).
    # 0 - без лимита трафика.
    total_bytes: int = Field(0, alias="totalGB")
    # Метка времени в миллисекундах; 0 - без срока действия.
    expiry_time: int = Field(0, alias="expiryTime")
    reset: int = Field(0, description="Период сброса счётчика трафика в днях")


class ClientRecord(BaseModel):
    """Клиент, как его отдаёт панель в ``GET /panel/api/clients/get/:email``.

    Важно: ``id`` здесь - числовой ID строки в БД панели, а UUID лежит в ``uuid``.
    В теле на запись (``XuiClientPayload``) UUID наоборот называется ``id``.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    email: str
    uuid: str = ""
    sub_id: str = Field("", alias="subId")
    flow: str = ""
    enable: bool = True
    tg_id: int = Field(0, alias="tgId")
    comment: str = ""
    group: str = ""
    limit_ip: int = Field(0, alias="limitIp")
    total_bytes: int = Field(0, alias="totalGB")
    expiry_time: int = Field(0, alias="expiryTime")
    reset: int = 0

    def to_payload(self) -> "XuiClientPayload":
        """Собрать тело для записи, не потеряв настройки, выставленные в панели руками."""
        return XuiClientPayload(
            id=self.uuid,
            email=self.email,
            subId=self.sub_id,
            flow=self.flow or DEFAULT_FLOW,
            enable=self.enable,
            tgId=self.tg_id,
            comment=self.comment,
            group=self.group,
            limitIp=self.limit_ip,
            totalGB=self.total_bytes,
            expiryTime=self.expiry_time,
            reset=self.reset,
        )


class ClientTraffic(BaseModel):
    """Ответ ``GET /panel/api/clients/traffic/:email``."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    email: str = ""
    enable: bool = False
    up: int = 0
    down: int = 0
    total: int = 0
    expiry_time: int = Field(0, alias="expiryTime")
    reset: int = 0
    last_online: int = Field(0, alias="lastOnline")

    @property
    def used_bytes(self) -> int:
        """Потрачено с последнего сброса счётчика (панель сбрасывает раз в ``reset`` дней)."""
        return self.up + self.down
