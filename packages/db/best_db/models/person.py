from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from best_db.models.base import Base

if TYPE_CHECKING:
    from best_db.models.lbg_member import LbgMember
    from best_db.models.place import Place
    from best_db.models.refund import Refund


class Person(Base):
    __tablename__ = "persons"
    __table_args__ = {"comment": "Человек"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False,
        comment="ID в Telegram",
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Имя пользователя",
    )
    telegram_username: Mapped[str | None] = mapped_column(
        String(32),
        index=True,
        nullable=True,
        comment="Telegram @username (для авто-связи с LbgMember)",
    )

    # Опциональная связь с участником локальной группы (если человек опознан).
    # Один-к-одному: одному Person соответствует не более одного LbgMember.
    lbg_member_id: Mapped[int | None] = mapped_column(
        ForeignKey("lbg_members.id", ondelete="SET NULL"),
        unique=True,
        index=True,
        nullable=True,
        comment="Связанный участник LBG (если опознан)",
    )
    lbg_member: Mapped["LbgMember | None"] = relationship(
        "LbgMember",
        back_populates="person",
    )

    # Закрепленное место
    places: Mapped[list["Place"]] = relationship("Place", back_populates="person")

    # Отношение к Refund
    refunds: Mapped[list["Refund"]] = relationship("Refund", back_populates="customer")
