from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from best_db.models.base import Base

if TYPE_CHECKING:
    from best_db.models.awg_device import AwgDevice
    from best_db.models.person import Person


class AwgAccess(Base):
    """Разрешение на AmneziaWG: бот заводит его сам активному мемберу - с первым устройством или рассылкой.

    В отличие от VLESS, один ключ AmneziaWG - одно устройство: на двух устройствах сразу
    они перебивают друг другу endpoint. Поэтому разрешение - это лимит устройств, а сами
    ключи (``AwgDevice``) человек заводит в боте по одному на устройство. Админ может отозвать
    разрешение (``revoked``) или выставить личный лимит.
    """

    __tablename__ = "awg_access"
    __table_args__ = {"comment": "Доступ мембера к AmneziaWG"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Уникальный ID разрешения")

    # Одно разрешение на человека: unique на FK.
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
        comment="Кому выдан доступ",
    )
    person: Mapped["Person"] = relationship("Person", back_populates="awg_access")

    status: Mapped[str] = mapped_column(
        String(16),
        default="granted",
        server_default="granted",
        index=True,
        nullable=False,
        comment="granted/suspended/revoked",
    )
    device_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Сколько устройств можно завести (NULL - лимит по умолчанию из настроек бота)",
    )

    # selectin: устройства нужны почти везде, где нужно разрешение, а ленивая подгрузка в async невозможна.
    devices: Mapped[list["AwgDevice"]] = relationship(
        "AwgDevice",
        back_populates="access",
        cascade="all, delete-orphan",
        order_by="AwgDevice.number",
        lazy="selectin",
    )

    # --- Служебное ---
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда админ выдал доступ",
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда ключи выключены (выбыл из LBG или отозван админом)",
    )
    announced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда человеку ушла рассылка о переезде AmneziaWG (повторно не шлём)",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
