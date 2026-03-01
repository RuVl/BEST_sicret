import typing

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base

if typing.TYPE_CHECKING:
    from database.models import Person, Payment


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = {"comment": "Возврат средств"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="Уникальный ID возврата")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Название товара")
    description: Mapped[str] = mapped_column(String, nullable=True, comment="Описание")

    # Связь с Person
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("persons.id"), nullable=False, comment="ID инициировавшего возврат")
    customer: Mapped['Person'] = relationship("Person", back_populates="refunds")

    # Связь с Payment (nullable=True, так как возврат может быть создан до привязки к платежу)
    payment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("payments.id"), nullable=True, comment="ID платежа, по которому осуществляется возврат")
    payment: Mapped['Payment | None'] = relationship("Payment", back_populates="refunds")
