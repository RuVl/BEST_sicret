from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import base, Person, Payment


class Refund(base):
    __tablename__ = "items"
    __table_args__ = {"comment": "Товарная единица"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Уникальный ID возврата")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Название товара")
    description: Mapped[str] = mapped_column(String, nullable=True, comment="Описание")

    # Связь с Person
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("person.id"), nullable=False,
                                             comment="ID инициировавшего возврат")
    customer: Mapped['Person'] = relationship("Person", back_populates="refunds")

    # Связь с Payment
    payment_id: Mapped[int] = mapped_column(Integer, ForeignKey("payment.id"), nullable=False,
                                            comment="ID платежа, по которому осуществляется возврат")
    payment: Mapped['Payment'] = relationship("payment", back_populates="refunds")
