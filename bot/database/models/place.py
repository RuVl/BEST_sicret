from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import base, person, item


class Place(base):
	__tablename__ = "placees"
	__table_args__ = {"comment": "Место хранения"}

	id: Mapped[int] = mapped_column(Integer, primary_key=True)
	address: Mapped[str] = mapped_column(String, nullable=False, comment="Адрес места хранения")

	person_id: Mapped[int] = mapped_column(Integer, ForeignKey("persons.id"), nullable=False, comment="у кого хранится")
	person: Mapped['person'] = relationship('Person', back_populates='places', foreign_keys=[person_id])

	# Отношение к Item
	items: Mapped[list["item"]] = relationship("Item", back_populates="place")