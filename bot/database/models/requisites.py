from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base
from database.models.person import Person


class Requisites(Base):
    __tablename__ = "requisites"
    __table_args__ = {"comment": "Платежные реквизиты"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Уникальный идентификатор реквизитов")
    details: Mapped[str] = mapped_column(String(255), nullable=False, comment="Подробная информация о реквизитах")

    # Отношение к Person
    person: Mapped['Person'] = relationship("Person", back_populates="requisites")
