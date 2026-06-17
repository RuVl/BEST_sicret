from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from best_db.models.base import Base

if TYPE_CHECKING:
    from best_db.models.item import Item
    from best_db.models.person import Person


class Place(Base):
    __tablename__ = "places"
    __table_args__ = {"comment": "Место хранения"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    address: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Адрес места хранения",
    )

    person_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("persons.id"),
        nullable=False,
        comment="у кого хранится",
    )
    person: Mapped["Person"] = relationship(
        "Person",
        back_populates="places",
        foreign_keys=[person_id],
    )

    # Отношение к Item
    items: Mapped[list["Item"]] = relationship("Item", back_populates="place")
