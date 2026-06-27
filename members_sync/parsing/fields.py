"""Канонические имена колонок и классификация секций → статус членства."""

# Канонические колонки (то, что мы ищем в заголовках листа).
NUMBER = "number"
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


# Известные секции → (membership_category, membership_status).
_SECTION_MAP: dict[str, tuple[str, str]] = {
    "board": ("board", "active"),
    "full members": ("full_member", "active"),
    "baby members": ("baby_member", "active"),
    "observers": ("observer", "active"),
    "alumni": ("alumni", "alumni"),
    "former": ("former", "inactive"),
    "abroad": ("abroad", "active"),
    "guests": ("guest", "active"),
    "guest": ("guest", "active"),
    "inactive": ("inactive", "inactive"),
    "ex-full members": ("ex_full_member", "ex"),
    "ex full members": ("ex_full_member", "ex"),
    "ex-baby members": ("ex_baby_member", "ex"),
    "ex baby members": ("ex_baby_member", "ex"),
    "ex-members": ("ex_member", "ex"),
}


def classify_section(section: str | None, default: tuple[str, str]) -> tuple[str, str]:
    """Секция → (category, status). Неизвестную секцию определяем эвристикой."""
    if not section:
        return default

    key = section.replace("\n", " ").strip().lower()
    if key in _SECTION_MAP:
        return _SECTION_MAP[key]

    # Эвристика для новых/изменённых секций.
    if key.startswith("ex"):
        return ("ex_member", "ex")
    if "alumni" in key:
        return ("alumni", "alumni")
    if "board" in key:
        return ("board", "active")
    if "full" in key:
        return ("full_member", "active")
    if "baby" in key:
        return ("baby_member", "active")
    if "observer" in key:
        return ("observer", "active")
    if "inactive" in key or "former" in key:
        return (key.split()[0], "inactive")
    return default


# Приоритет статусов при дедупе одного человека между листами (больше = важнее).
_STATUS_PRECEDENCE = {"active": 3, "alumni": 2, "ex": 1, "inactive": 0}


def status_precedence(status: str | None) -> int:
    return _STATUS_PRECEDENCE.get(status or "", -1)
