"""Описание раскладок листов.

Колонки сопоставляются по тексту заголовка (с запасным индексом), а не по
жёсткой позиции — это делает парсер устойчивым к перестановке/переименованию.

Раскладка A — лист «Database of Members».
Раскладка B — листы «Alumni…» и «Ex-members» (общая структура).
"""

from dataclasses import dataclass

from parsing import fields as F


@dataclass(frozen=True)
class ColumnDef:
    name: str
    aliases: tuple[str, ...]
    fallback_index: int | None = None
    required: bool = False


@dataclass(frozen=True)
class SheetSpec:
    layout: str
    header_row: int
    number_col: int  # колонка с № участника (признак основной строки)
    columns: tuple[ColumnDef, ...]
    default_membership: F.Membership  # членство, если секции в листе нет


_NAME = ("фио", "name", "ф.и.о")
_PHONE = ("телефон", "phone")
_EMAIL = ("gmail", "email", "mail", "почта")
_STATUS = ("status", "статус")
_BIRTHDAY = ("birthday", "дата рожд", "др ")
_ANGEL = ("angel", "ангел", "ментор")
_FACULTY = ("институт", "факультет", "faculty")
_HOME = ("home address", "адрес", "общеж")
_LOCAL = ("local involvement", "local", "локальн")
_INTL = ("international involvement", "international", "междунар")
_EVENTS = ("best events", "events participated", "мероприят")
_INSTA = ("instagram", "инстаграм", "инст")
_GENDER = ("пол", "gender", "sex")
_WORKPLACE = ("место работы", "работа", "workplace", "company")


# Раскладка A: page1 (Database of Members)
LAYOUT_A = SheetSpec(
    layout="A",
    header_row=0,
    number_col=0,
    default_membership=F.Membership("full_member", is_active=True),
    columns=(
        ColumnDef(F.NAME, _NAME, 1, required=True),
        ColumnDef(F.PHONE, _PHONE, 2),
        ColumnDef(F.SOCIAL, ("вконтакте", "vk", "telegram"), 3),
        ColumnDef(F.EMAIL, _EMAIL, 4, required=True),
        ColumnDef(F.STATUS_FIELD, _STATUS, 5),
        ColumnDef(F.BIRTHDAY, _BIRTHDAY, 6),
        ColumnDef(F.ACTIVE_PERIOD, ("начало активности", "active best", "since"), 7),
        ColumnDef(F.ANGEL, _ANGEL, 8),
        ColumnDef(F.FACULTY_GROUP, _FACULTY, 9),
        ColumnDef(F.HOME_ADDRESS, _HOME, 10),
        ColumnDef(F.LOCAL_INVOLVEMENT, _LOCAL, 11),
        ColumnDef(F.BEST_EVENTS, _EVENTS, 12),
        ColumnDef(F.INTERNATIONAL_INVOLVEMENT, _INTL, 13),
        ColumnDef(F.INSTAGRAM, _INSTA, 14),
        ColumnDef(F.GENDER, _GENDER, 15),
    ),
)

# Раскладка B: page2/page3 (Alumni…, Ex-members)
LAYOUT_B = SheetSpec(
    layout="B",
    header_row=0,
    number_col=0,
    default_membership=F.Membership("alumni"),
    columns=(
        ColumnDef(F.NAME, _NAME, 1, required=True),
        ColumnDef(F.PHONE, _PHONE, 2),
        ColumnDef(F.EMAIL, _EMAIL, 3, required=True),
        ColumnDef(F.STATUS_FIELD, _STATUS, 4),
        ColumnDef(F.BIRTHDAY, _BIRTHDAY, 5),
        ColumnDef(F.ACTIVE_PERIOD, ("active best", "since", "начало активности"), 6),
        ColumnDef(F.ANGEL, _ANGEL, 7),
        ColumnDef(F.FACULTY_GROUP, _FACULTY, 8),
        ColumnDef(F.SOCIAL, ("вконтакте", "vk", "facebook", "telegram"), 9),
        ColumnDef(F.LOCAL_INVOLVEMENT, _LOCAL, 10),
        ColumnDef(F.INTERNATIONAL_INVOLVEMENT, _INTL, 11),
        ColumnDef(F.BEST_EVENTS, _EVENTS, 12),
        ColumnDef(F.HOME_ADDRESS, _HOME, 13),
        ColumnDef(F.WORKPLACE, _WORKPLACE, 14),
        ColumnDef(F.INSTAGRAM, _INSTA, 15),
    ),
)


def spec_for_title(title: str) -> SheetSpec | None:
    """Подобрать раскладку по названию листа (источник истины — сам лист)."""
    low = title.strip().lower()
    if "database of members" in low:
        return LAYOUT_A
    if "ex-member" in low or "ex member" in low:
        return SheetSpec(
            layout="B-ex",
            header_row=LAYOUT_B.header_row,
            number_col=LAYOUT_B.number_col,
            columns=LAYOUT_B.columns,
            default_membership=F.Membership("ex_member", is_excluded=True),
        )
    if any(k in low for k in ("alumni", "former", "abroad", "guest", "inactive")):
        return LAYOUT_B
    return None
