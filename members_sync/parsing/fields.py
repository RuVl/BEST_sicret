"""Канонические имена колонок и классификация секций → членство."""

from dataclasses import dataclass

# Канонические колонки (то, что мы ищем в заголовках листа).
NAME = "name"
PHONE = "phone"
SOCIAL = "social"
EMAIL = "email"
STATUS_FIELD = "status_field"
BIRTHDAY = "birthday"
ACTIVE_PERIOD = "active_period"
ANGEL = "angel"
FACULTY_GROUP = "faculty_group"
HOME_ADDRESS = "home_address"
LOCAL_INVOLVEMENT = "local_involvement"
INTERNATIONAL_INVOLVEMENT = "international_involvement"
BEST_EVENTS = "best_events"
INSTAGRAM = "instagram"
GENDER = "gender"
WORKPLACE = "workplace"


@dataclass(frozen=True)
class Membership:
    """Членство, выведенное из секции листа.

    ``is_active`` - может брать таски группы, ``is_excluded`` - больше в ней не состоит.
    Alumni и former не активны, но и не исключены: доступ к ресурсам у них остаётся.
    """

    category: str
    is_active: bool = False
    is_excluded: bool = False


def _active(category: str) -> Membership:
    return Membership(category, is_active=True)


def _excluded(category: str) -> Membership:
    return Membership(category, is_excluded=True)


# Известные секции → членство.
_SECTION_MAP: dict[str, Membership] = {
    "board": _active("board"),
    "full members": _active("full_member"),
    "baby members": _active("baby_member"),
    "observers": _active("observer"),
    "alumni": Membership("alumni"),
    "former": Membership("former"),
    "abroad": _active("abroad"),
    "guests": _active("guest"),
    "guest": _active("guest"),
    "inactive": Membership("inactive"),
    "ex-full members": _excluded("ex_full_member"),
    "ex full members": _excluded("ex_full_member"),
    "ex-baby members": _excluded("ex_baby_member"),
    "ex baby members": _excluded("ex_baby_member"),
    "ex-members": _excluded("ex_member"),
}


def classify_section(section: str | None, default: Membership) -> Membership:
    """Секция → членство. Неизвестную секцию определяем эвристикой."""
    if not section:
        return default

    key = section.replace("\n", " ").strip().lower()
    if key in _SECTION_MAP:
        return _SECTION_MAP[key]

    # Эвристика для новых/изменённых секций.
    if key.startswith("ex"):
        return _excluded("ex_member")
    if "alumni" in key:
        return Membership("alumni")
    if "board" in key:
        return _active("board")
    if "full" in key:
        return _active("full_member")
    if "baby" in key:
        return _active("baby_member")
    if "observer" in key:
        return _active("observer")
    if "inactive" in key or "former" in key:
        return Membership(key.split()[0])
    return default


# Приоритет при дедупе одного человека между листами (больше = важнее).
# Alumni важнее former/inactive: у него больше шансов быть свежей записью.
_CATEGORY_PRECEDENCE = {"alumni": 2}


def membership_precedence(membership: Membership) -> int:
    """Чем весомее запись, тем выше число. Исключение перебивается любой другой секцией."""
    if membership.is_excluded:
        return 0
    if membership.is_active:
        return 3
    return _CATEGORY_PRECEDENCE.get(membership.category, 1)
