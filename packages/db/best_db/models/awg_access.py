from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from best_db.models.base import Base

if TYPE_CHECKING:
    from best_db.models.person import Person


class AwgAccess(Base):
    """Разрешение на AmneziaWG, выданное админом поверх VLESS-подписки.

    Ключ в веб-панели AmneziaWG заводится лениво - при первом запросе конфига в боте.
    Включён ли ключ, знает только панель; здесь лежат имя клиента и решение админа.
    """

    __tablename__ = "awg_access"
    __table_args__ = {"comment": "Доступ к AmneziaWG, выданный админом"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Уникальный ID разрешения")

    # Один ключ AmneziaWG на человека: unique на FK.
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
        comment="Кому выдан доступ",
    )
    person: Mapped["Person"] = relationship("Person", back_populates="awg_access")

    # Ограничения установщика AmneziaWG: [a-zA-Z0-9_-], не длиннее 15 символов.
    client_name: Mapped[str] = mapped_column(
        String(15),
        unique=True,
        nullable=False,
        comment="Имя клиента в AmneziaWG (lbg<person_id> или заданное админом)",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        default="granted",
        server_default="granted",
        index=True,
        nullable=False,
        comment="granted/suspended/revoked",
    )

    # --- Служебное ---
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда админ выдал доступ",
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда конфиг последний раз отправлен человеку",
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда ключ выключен (выбыл из LBG или отозван админом)",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
