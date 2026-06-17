from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from best_db.models.base import Base

if TYPE_CHECKING:
    from best_db.models.person import Person


class LbgMember(Base):
    """Участник локальной группы BEST, синхронизированный из Google Sheets.

    Одна денормализованная таблица: типизированные поля + ``raw`` (полный сырой
    слепок строк таблицы). Категории/статусы — строки (без DB-enum), чтобы новые
    секции в таблице не требовали миграции. Заполняется сервисом ``members_sync``;
    ``bot`` читает её и опционально связывает с :class:`Person`.
    """

    __tablename__ = "lbg_members"
    __table_args__ = {"comment": "Участник LBG (синхронизация из Google Sheets)"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # --- Идентичность и upsert ---
    identity_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Ключ сопоставления: best-email или нормализованное ФИО",
    )

    # --- Имя ---
    full_name_ru: Mapped[str | None] = mapped_column(String(255), comment="ФИО на русском")
    full_name_en: Mapped[str | None] = mapped_column(String(255), comment="ФИО на английском")
    gender: Mapped[str | None] = mapped_column(String(16), comment="male/female")

    # --- Контакты ---
    best_email: Mapped[str | None] = mapped_column(String(255), index=True, comment="Почта @best-eu.org")
    personal_email: Mapped[str | None] = mapped_column(String(255), comment="Личная почта")
    phone: Mapped[str | None] = mapped_column(String(32), comment="Нормализованный телефон")
    phone_raw: Mapped[str | None] = mapped_column(String(255), comment="Телефон как в таблице")
    vk_url: Mapped[str | None] = mapped_column(String(255), comment="ВКонтакте")
    telegram: Mapped[str | None] = mapped_column(String(255), comment="Telegram")
    facebook: Mapped[str | None] = mapped_column(String(255), comment="Facebook")
    instagram: Mapped[str | None] = mapped_column(String(255), comment="Instagram")

    # --- Учёба ---
    faculty: Mapped[str | None] = mapped_column(String(255), comment="Институт/факультет")
    study_group: Mapped[str | None] = mapped_column(String(64), comment="Учебная группа")

    # --- Прочее ---
    home_address: Mapped[str | None] = mapped_column(Text, comment="Домашний адрес / общежитие")
    dormitory: Mapped[str | None] = mapped_column(String(255), comment="Общежитие (если выделено)")
    angel_name: Mapped[str | None] = mapped_column(String(255), comment="Ангел/ментор")
    status_field: Mapped[str | None] = mapped_column(Text, comment="Должность/роли (Status/field)")

    birthday: Mapped[date | None] = mapped_column(Date, comment="Дата рождения")
    birthday_raw: Mapped[str | None] = mapped_column(String(64), comment="Дата рождения как в таблице")

    active_since: Mapped[date | None] = mapped_column(Date, comment="Начало активности")
    active_since_raw: Mapped[str | None] = mapped_column(String(64))
    active_till: Mapped[date | None] = mapped_column(Date, comment="Окончание активности")
    active_till_raw: Mapped[str | None] = mapped_column(String(64))

    local_involvement: Mapped[str | None] = mapped_column(Text)
    international_involvement: Mapped[str | None] = mapped_column(Text)
    best_events: Mapped[str | None] = mapped_column(Text)
    workplace: Mapped[str | None] = mapped_column(Text)

    # --- Статус членства ---
    membership_category: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        comment="board/full_member/baby_member/observer/alumni/ex_*/inactive",
    )
    membership_status: Mapped[str | None] = mapped_column(
        String(32),
        index=True,
        comment="Грубый статус: active/alumni/ex/inactive",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, comment="Активный член")

    # --- Источник ---
    source_sheet: Mapped[str | None] = mapped_column(String(255), comment="Имя листа-источника")
    source_section: Mapped[str | None] = mapped_column(String(255), comment="Секция листа")
    source_row_start: Mapped[int | None] = mapped_column(Integer, comment="Первая строка в таблице")
    source_row_end: Mapped[int | None] = mapped_column(Integer, comment="Последняя строка в таблице")
    raw: Mapped[dict] = mapped_column(JSONB, comment="Полный сырой слепок строк")

    # --- Служебное ---
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Первое появление в таблице",
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Последнее появление в таблице",
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Последний прогон синхронизации",
    )
    removed_from_sheet_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Когда пропал из таблицы",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Обратная сторона опциональной связи Person.lbg_member (один-к-одному).
    person: Mapped["Person | None"] = relationship(
        "Person",
        back_populates="lbg_member",
        uselist=False,
    )
