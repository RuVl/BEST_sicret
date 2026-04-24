from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base
from database.models.refund import Refund


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = {"comment": "Платеж"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Уникальный ID платежа")
    cost: Mapped[int] = mapped_column(Integer, nullable=False, comment="Стоимость")
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Статус оплаты")
    created_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="Дата создания записи о платеже")

    # Был запрос на чек в виде фото, но пока оставила как ссылку
    bill: Mapped[str] = mapped_column(String(255), nullable=True, comment="Ссылка на чек")
    payed_date: Mapped[datetime] = mapped_column(DateTime, nullable=True, comment="Дата фактической оплаты")

    # Отношение к Refund
    refunds: Mapped[list['Refund']] = relationship("refund", back_populates="payment")
