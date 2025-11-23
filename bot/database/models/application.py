import typing
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, DateTime, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base

if typing.TYPE_CHECKING:
    from database.models import Person, Item

# Промежуточная таблица для связи Application и Item (многие-ко-многим)
application_item = Table(
    'application_items',
    Base.metadata,
    Column('application_id', Integer, ForeignKey('applications.id'), primary_key=True),
    Column('item_id', Integer, ForeignKey('items.id'), primary_key=True),
    Column('quantity', Integer, nullable=False, comment='Количество запрашиваемого предмета'),
)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = {"comment": "Заявка на использование имущества"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    applicant_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Имя заявителя")
    purpose: Mapped[str] = mapped_column(String(500), nullable=False, comment="Цель взятия имущества")
    status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False, comment="Статус заявки (pending, approved, rejected)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False, comment="Дата создания заявки")

    # Связь с Person
    person_id: Mapped[int] = mapped_column(Integer, ForeignKey("persons.id"), nullable=False, comment="ID пользователя, создавшего заявку")
    person: Mapped['Person'] = relationship("Person", back_populates="applications", foreign_keys=[person_id])

    # Связь многие-ко-многим с Item через промежуточную таблицу
    items: Mapped[list['Item']] = relationship(
        "Item",
        secondary=application_item,
        back_populates="applications"
    )


