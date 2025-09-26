from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import base, place, requisites, refund


class Person(Base):
	__tablename__ = "persons"
	__table_args__ = {"comment": "Человек"}

	id: Mapped[int] = mapped_column(Integer, primary_key=True)
	telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False, comment="ID в Telegram")
	full_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Имя пользователя")

	# Закрепленное место
	places: Mapped[list['place']] = relationship('Place', back_populates='person')

	# Связь Requisites
	requisites: Mapped["requisites"] = relationship("Requisites", back_populates="person")
	payment_id: Mapped[int] = mapped_column(Integer, ForeignKey("requisites.id"), unique=True, nullable=True, comment="ID реквизитов")

	# Отношение к Refund
    refunds: Mapped[list["refund"]] = relationship("Refund", back_populates="customer")