from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base
from database.models.place import Place
from database.models.refund import Refund


class Person(Base):
    __tablename__ = "persons"
    __table_args__ = {"comment": "Человек"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        Integer, unique=True, index=True, nullable=False, comment="ID в Telegram"
    )
    full_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Имя пользователя"
    )

    # Закрепленное место
    places: Mapped[list["Place"]] = relationship("Place", back_populates="person")

    # Отношение к Refund
    refunds: Mapped[list["Refund"]] = relationship("Refund", back_populates="customer")
