"""Схемы обмена с панелью 3x-ui (v3).

Поля повторяют Go-структуры панели: ``model.Client`` и ``xray.ClientTraffic``.
Панель отдаёт всё в конверте ``{success, msg, obj}`` - его разбирает ``client.py``.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class BulkSkip(BaseModel):
    """Клиент, которого панель пропустила в ``bulkEnable``/``bulkDisable``, и причина."""

    email: str
    reason: str = ""


class BulkSetEnableResult(BaseModel):
    """Ответ ``POST /panel/api/clients/bulkEnable|bulkDisable`` (``service.BulkSetEnableResult``).

    Провал по отдельному email панель не считает ошибкой запроса: ``success=true``, а email -
    в ``skipped``. Для нас это неуспех именно этих клиентов.
    """

    changed: int = 0
    skipped: list[BulkSkip] = Field(default_factory=list)

    @field_validator("skipped", mode="before")
    @classmethod
    def null_is_empty(cls, value: Any) -> Any:
        # skipped в Go с omitempty, но nil-слайс без него пришёл бы null.
        return [] if value is None else value


class ClientDetails(BaseModel):
    """Ответ ``GET /panel/api/clients/get/:email``: клиент и инбаунды, к которым он привязан.

    ``client`` оставляем словарём: VLESS читает из него ``ClientRecord``, AmneziaWG - ``AwgPeer``.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    client: dict[str, Any]
    inbound_ids: list[int] = Field(default_factory=list, alias="inboundIds")
    # Адрес клиента в каждом туннельном инбаунде (WireGuard/AmneziaWG): ``{"3": "10.70.0.2/32"}``.
    tunnel_allowed_ips: dict[str, str | list[str]] = Field(default_factory=dict, alias="tunnelAllowedIPs")

    @field_validator("inbound_ids", mode="before")
    @classmethod
    def null_list_is_empty(cls, value: Any) -> Any:
        # Go сериализует nil-слайс как null - это «пусто», а не испорченный ответ.
        return [] if value is None else value

    @field_validator("tunnel_allowed_ips", mode="before")
    @classmethod
    def null_map_is_empty(cls, value: Any) -> Any:
        # То же для nil-map: у клиента без туннельных инбаундов адресов просто нет.
        return {} if value is None else value

    @property
    def record(self) -> ClientRecord:
        return ClientRecord.model_validate(self.client)

    def update_body(self, **changes: Any) -> dict[str, Any]:
        """Тело для ``/clients/update``: клиент как есть плюс правки (ключи - имена полей панели).

        Панель заменяет клиента телом запроса, поэтому шлём все поля, что она отдала, - и те,
        которых нет в наших моделях (пароли других протоколов, выставленное в админке руками).
        На запись UUID называется ``id``, а числовой ``id`` строки панели не нужен.
        """
        body = {key: value for key, value in self.client.items() if key not in ("id", "uuid")}
        body["id"] = self.client.get("uuid", "")
        return _to_go_client(body | changes)


def _to_go_client(body: dict[str, Any]) -> dict[str, Any]:
    """Привести поля к типам ``model.Client``, в который панель разбирает тело ``/clients/update``.

    GET отдаёт ``model.ClientRecord`` - строку таблицы, где часть полей хранится иначе, чем
    принимает запись. Расхождение панель не прощает: ``json: cannot unmarshal string into Go
    struct field Client.allowedIPs of type []string`` - и update падает целиком.
    """
    # В БД панели адреса - одна строка через запятую (strings.Join(..., ",")), на запись - []string.
    allowed_ips = body.get("allowedIPs")
    if allowed_ips is None or isinstance(allowed_ips, str):
        body["allowedIPs"] = [ip.strip() for ip in (allowed_ips or "").split(",") if ip.strip()]

    # reverse панель отдаёт объектом (или null), а принимает в *ClientReverse. Строкой он приходит,
    # только если в колонке лежит не JSON: такое значение панель и сама не прочтёт - не шлём его.
    if "reverse" in body and not isinstance(body["reverse"], dict | None):
        del body["reverse"]
    return body
