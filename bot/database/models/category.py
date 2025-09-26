from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base, Item


class Category(Base):
	__tablename__ = "categories"
	__table_args__ = {"comment": "Название категории"}

	id: Mapped[int] = mapped_column(Integer, primary_key=True)
	name: Mapped[str] = mapped_column(String(255), nullable=False, comment="название группы товаров")

	# Back ref items.category_id -> categories.id
	items: Mapped[list['Item']] = relationship('Item', back_populates='category')
