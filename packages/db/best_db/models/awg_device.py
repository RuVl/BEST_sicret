from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from best_db.models.base import Base

if TYPE_CHECKING:
    from best_db.models.awg_access import AwgAccess


class AwgDevice(Base):
    """Устройство с собственным ключом AmneziaWG (пир в веб-панели AmneziaWG).

    Включён ли ключ, знает только панель; здесь - номер устройства и имя клиента.
    """

    __tablename__ = "awg_devices"
    __table_args__ = (
        UniqueConstraint("access_id", "number"),
        {"comment": "Устройство с ключом AmneziaWG"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Уникальный ID устройства")

    access_id: Mapped[int] = mapped_column(
        ForeignKey("awg_access.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Разрешение, по которому заведено устройство",
    )
    access: Mapped["AwgAccess"] = relationship("AwgAccess", back_populates="devices")

    number: Mapped[int] = mapped_column(Integer, nullable=False, comment="Номер устройства у человека (с 1)")

    # Ограничения установщика AmneziaWG: [a-zA-Z0-9_-], не длиннее 15 символов.
    client_name: Mapped[str] = mapped_column(
        String(15),
        unique=True,
        nullable=False,
        comment="Имя клиента в AmneziaWG (lbg<person_id>-<number>)",
    )

    # Название задаёт сам человек (``Телефон``, ``Ноутбук``); NULL - «Устройство <number>».
    label: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="Название устройства от владельца")

    # --- Служебное ---
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда конфиг последний раз отправлен человеку",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
