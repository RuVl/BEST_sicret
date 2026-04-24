from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base
from database.models.category import Category
from database.models.place import Place


class Item(Base):
    __tablename__ = "items"
    __table_args__ = {"comment": "Товарная единица"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="название товара")
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="количество товара")
    unit: Mapped[str] = mapped_column(String(255), nullable=False, comment="единица измерения")

    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False,
                                             comment="к какой категории относится")
    category: Mapped['Category'] = relationship('Category', back_populates='items', foreign_keys=[category_id])

    place_id: Mapped[int] = mapped_column(Integer, ForeignKey("places.id"), nullable=False, comment="где хранится")
    place: Mapped['Place'] = relationship('Place', back_populates='items', foreign_keys=[place_id])
