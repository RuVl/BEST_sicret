from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.models import Base


class Requisites(Base):
    __tablename__ = "requisites"
    __table_args__ = {"comment": "Платежные реквизиты"}

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, comment="Уникальный идентификатор реквизитов"
    )
    details: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Подробная информация о реквизитах"
    )
