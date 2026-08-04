from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from best_db.models.base import Base

if TYPE_CHECKING:
    from best_db.models.person import Person


class VpnSubscription(Base):
    """VPN-подписка мембера, выданная ботом через панель 3x-ui.

    Трафик и признак ``enable`` намеренно не дублируются: источник правды — панель,
    бот хранит только идентификаторы клиента и собственный статус выдачи.
    """

    __tablename__ = "vpn_subscriptions"
    __table_args__ = {"comment": "VPN-подписка, выданная ботом"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Уникальный ID подписки")

    # Одна подписка на человека: unique на FK.
    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
        comment="Владелец подписки",
    )
    person: Mapped["Person"] = relationship("Person", back_populates="vpn_subscription")

    # --- Идентификаторы клиента в панели 3x-ui ---
    xui_email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Идентификатор клиента в панели (best-почта или lbg-<person_id>)",
    )
    sub_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="subId клиента — ключ ссылки-подписки",
    )
    xui_client_uuid: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="UUID клиента в панели (поле id)",
    )

    protocol: Mapped[str] = mapped_column(
        String(16),
        default="xui",
        server_default="xui",
        nullable=False,
        comment="Тип подписки: xui (задел под awg)",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="active",
        server_default="active",
        index=True,
        nullable=False,
        comment="active/revoked",
    )

    # --- Служебное ---
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда подписка выдана",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда подписка отключена",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
