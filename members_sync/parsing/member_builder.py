"""Сборка ``ParsedMember`` из сырой 2-строчной записи таблицы."""

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from parsing import fields as F
from parsing.issues import IssueCollector
from parsing.normalizers import (
    classify_faculty_group,
    classify_name,
    classify_socials,
    extract_dormitory,
    extract_emails,
    extract_instagram,
    normalize_identity_name,
    normalize_phone,
    parse_active_period,
    parse_date,
    parse_gender,
)

if TYPE_CHECKING:
    from sheets.record_reader import RawRecord
    from sheets.spec import SheetSpec


@dataclass
class ParsedMember:
    identity_key: str
    full_name_ru: str | None = None
    full_name_en: str | None = None
    gender: str | None = None
    best_email: str | None = None
    personal_email: str | None = None
    phone: str | None = None
    phone_raw: str | None = None
    vk_url: str | None = None
    telegram: str | None = None
    facebook: str | None = None
    instagram: str | None = None
    faculty: str | None = None
    study_group: str | None = None
    home_address: str | None = None
    dormitory: str | None = None
    angel_name: str | None = None
    status_field: str | None = None
    birthday: date | None = None
    birthday_raw: str | None = None
    active_since: date | None = None
    active_since_raw: str | None = None
    active_till: date | None = None
    active_till_raw: str | None = None
    local_involvement: str | None = None
    international_involvement: str | None = None
    best_events: str | None = None
    workplace: str | None = None
    membership_category: str | None = None
    membership_status: str | None = None
    is_active: bool = False
    source_sheet: str | None = None
    source_section: str | None = None
    source_row_start: int | None = None
    source_row_end: int | None = None
    raw: dict = field(default_factory=dict)

    def to_db_values(self) -> dict:
        """Значения для колонок модели Member (служебные timestamp'ы ставит upsert)."""
        return asdict(self)


def _combine(p: str, s: str) -> str | None:
    parts = [x.strip() for x in (p, s) if x and x.strip()]
    # Не дублируем одинаковые значения из обеих строк.
    seen: list[str] = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    return "\n".join(seen) or None


def build(record: "RawRecord", spec: "SheetSpec", issues: IssueCollector) -> ParsedMember | None:
    """RawRecord → ParsedMember (+ issues). None, если нет даже идентичности."""
    sheet = record.sheet_title

    def pair(column: str) -> tuple[str, str]:
        return record.raw_pair(column)

    # Имя.
    name_p, name_s = pair(F.NAME)
    full_name_ru, full_name_en = classify_name([name_p, name_s])

    # Email.
    email_p, email_s = pair(F.EMAIL)
    best_email, personal_email, email_msg = extract_emails([email_p, email_s])
    if email_msg:
        issues.add(sheet, F.EMAIL, email_msg, record.a1(F.EMAIL))

    # Идентичность.
    identity = best_email or normalize_identity_name(full_name_ru or full_name_en)
    if not identity:
        issues.add(
            sheet,
            "identity",
            "нет ни best-email, ни ФИО — запись пропущена",
            record.a1(F.NAME),
            level="error",
        )
        return None

    # Телефон.
    phone_p, phone_s = pair(F.PHONE)
    phone, phone_raw, phone_msg = normalize_phone(_combine(phone_p, phone_s) or "")
    if phone_msg:
        issues.add(sheet, F.PHONE, phone_msg, record.a1(F.PHONE))

    # Соцсети.
    social_p, social_s = pair(F.SOCIAL)
    socials = classify_socials([social_p, social_s])

    # Учёба.
    fac_p, fac_s = pair(F.FACULTY_GROUP)
    faculty, study_group = classify_faculty_group([fac_p, fac_s])

    # Дата рождения.
    bday_p, _ = pair(F.BIRTHDAY)
    birthday, bday_msg = parse_date(bday_p)
    if bday_msg:
        issues.add(sheet, F.BIRTHDAY, bday_msg, record.a1(F.BIRTHDAY))

    # Период активности.
    period_p, _ = pair(F.ACTIVE_PERIOD)
    since, since_raw, till, till_raw, period_msg = parse_active_period(period_p)
    if period_msg:
        issues.add(sheet, F.ACTIVE_PERIOD, period_msg, record.a1(F.ACTIVE_PERIOD))

    # Пол.
    gender_p, _ = pair(F.GENDER)
    gender, gender_msg = parse_gender(gender_p)
    if gender_msg:
        issues.add(sheet, F.GENDER, gender_msg, record.a1(F.GENDER))

    # Адрес / общежитие.
    addr = _combine(*pair(F.HOME_ADDRESS))
    dormitory = extract_dormitory(addr)

    # Категория/статус по секции.
    category, status = F.classify_section(record.section, spec.default_category)

    member = ParsedMember(
        identity_key=identity,
        full_name_ru=full_name_ru,
        full_name_en=full_name_en,
        gender=gender,
        best_email=best_email,
        personal_email=personal_email,
        phone=phone,
        phone_raw=phone_raw,
        vk_url=socials["vk"],
        telegram=socials["telegram"],
        facebook=socials["facebook"],
        instagram=extract_instagram(list(pair(F.INSTAGRAM))),
        faculty=faculty,
        study_group=study_group,
        home_address=addr,
        dormitory=dormitory,
        angel_name=_combine(*pair(F.ANGEL)),
        status_field=_combine(*pair(F.STATUS_FIELD)),
        birthday=birthday,
        birthday_raw=bday_p or None,
        active_since=since,
        active_since_raw=since_raw,
        active_till=till,
        active_till_raw=till_raw,
        local_involvement=_combine(*pair(F.LOCAL_INVOLVEMENT)),
        international_involvement=_combine(*pair(F.INTERNATIONAL_INVOLVEMENT)),
        best_events=_combine(*pair(F.BEST_EVENTS)),
        workplace=_combine(*pair(F.WORKPLACE)),
        membership_category=category,
        membership_status=status,
        is_active=(status == "active"),
        source_sheet=sheet,
        source_section=record.section,
        source_row_start=record.primary_row,
        source_row_end=record.secondary_row or record.primary_row,
        raw=record.snapshot(),
    )
    return member
