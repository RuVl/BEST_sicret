"""Чистые функции нормализации «грязных» значений из таблицы.

Контракт: ни одна функция не бросает исключение на плохих данных. Где разбор
неоднозначен или невозможен — возвращается ``None`` и человекочитаемое сообщение,
а сырое значение сохраняется выше по стеку.
"""

import re
from datetime import date, datetime

import phonenumbers

# --- общее ---------------------------------------------------------------

_CYR = re.compile(r"[А-Яа-яЁё]")
_LAT = re.compile(r"[A-Za-z]")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_WS = re.compile(r"\s+")


def normalize_header(value: str) -> str:
    """Заголовок → канонический вид для сопоставления (нижний регистр, без \\n, ё→е)."""
    value = (value or "").replace("\n", " ").replace("ё", "е").replace("Ё", "Е")
    return _WS.sub(" ", value).strip().lower()


def normalize_identity_name(name: str | None) -> str:
    """ФИО → ключ идентичности (нижний регистр, схлопнутые пробелы, ё→е)."""
    if not name:
        return ""
    name = name.replace("ё", "е").replace("Ё", "Е")
    return _WS.sub(" ", name).strip().lower()


def _script_counts(value: str) -> tuple[int, int]:
    return len(_CYR.findall(value)), len(_LAT.findall(value))


def classify_name(values: list[str]) -> tuple[str | None, str | None]:
    """Из значений колонки имени выделить русское и английское ФИО по алфавиту.

    Устойчиво к перестановке строк (рус. имя бывает во второй строке).
    """
    ru: str | None = None
    en: str | None = None
    for value in values:
        value = (value or "").strip()
        if not value:
            continue
        cyr, lat = _script_counts(value)
        if cyr >= lat and cyr > 0 and ru is None:
            ru = value
        elif lat > cyr and en is None:
            en = value
        elif ru is None and cyr > 0:
            ru = value
    return ru, en


# --- телефон -------------------------------------------------------------


def _e164_candidate(cand: str) -> str | None:
    """Сырой кусок → E.164-строка по однозначным правилам (или ``None``).

    Страну угадываем только когда это явно следует из самого номера: ведущий ``+``,
    международный префикс ``00`` или российские формы (8/7 + 10 цифр, либо 10 цифр).
    Голый ``32485939831`` без ``+`` намеренно не превращаем в Бельгию — это догадка.
    """
    has_plus = "+" in cand
    digits = re.sub(r"\D", "", cand)
    if has_plus:
        return "+" + digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    return None


def normalize_phone(raw: str) -> tuple[str | None, str | None, str | None]:
    """(нормализованный, сырой, сообщение). Берёт первый валидный телефон.

    Валидность (в т.ч. длину по стране) проверяет ``phonenumbers``; поддерживаются
    иностранные номера в международном формате, а не только российские.
    """
    raw = (raw or "").strip()
    if not raw:
        return None, None, None

    # Несколько номеров в одной ячейке (или номер из вторичной строки, склеенный через \n
    # в member_builder) разбираем построчно — иначе соседние номера слипаются в один.
    for line in raw.splitlines():
        for cand in re.findall(r"[+\d][\d()\-\s]{8,}", line):
            e164 = _e164_candidate(cand)
            if e164 is None:
                continue
            try:
                parsed = phonenumbers.parse(e164, None)
            except phonenumbers.NumberParseException:
                continue
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164), raw, None
    return None, raw, "не удалось нормализовать телефон"


# --- даты ----------------------------------------------------------------

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _two_digit_year(year: int) -> int:
    if year < 100:
        return 2000 + year if year <= 30 else 1900 + year
    return year


def parse_date(raw: str) -> tuple[date | None, str | None]:
    """Разобрать дату рождения. Поддержка d.m.y, m/d/y (US), y-m-d, 2-значных лет."""
    raw = (raw or "").strip()
    if not raw:
        return None, None

    # Полная дата-время вида "3/1/2018 0:00:00" → берём дату.
    token = raw.split()[0]

    groups = re.split(r"[.\-/]", token)
    if len(groups) == 3 and all(g.isdigit() for g in groups):
        a, b, c = (int(g) for g in groups)
        # Определяем, где год.
        if a > 31:  # y-m-d
            year, month, day = _two_digit_year(a), b, c
        else:  # d/m/y или m/d/y
            year = _two_digit_year(c)
            if a > 12 >= b or (a > 12 and b <= 12):
                day, month = a, b
            elif b > 12 >= a:
                day, month = b, a  # американский m/d/y
            else:
                day, month = a, b  # неоднозначно → считаем европейским d.m
        try:
            return date(year, month, day), None
        except ValueError:
            return None, f"некорректная дата: {raw!r}"

    # Текстовые форматы.
    for fmt in ("%B %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(token, fmt).date(), None
        except ValueError:
            continue
    return None, f"не распознан формат даты: {raw!r}"


def _parse_month_year(part: str) -> date | None:
    part = part.strip().strip("'")
    if not part:
        return None
    # "Sep 22'" → Sep 2022
    m = re.match(r"([A-Za-z]+)\.?\s*'?(\d{2,4})'?", part)
    if m:
        month = _MONTHS.get(m.group(1).lower()[:3]) or _MONTHS.get(m.group(1).lower())
        if month:
            year = _two_digit_year(int(m.group(2)))
            try:
                return date(year, month, 1)
            except ValueError:
                return None
    # Иногда полноценная дата.
    parsed, _ = parse_date(part)
    return parsed


def parse_active_period(
    raw: str,
) -> tuple[date | None, str | None, date | None, str | None, str | None]:
    """(since, since_raw, till, till_raw, message). Период «X - Y» или одиночное «X»."""
    raw = (raw or "").strip()
    if not raw:
        return None, None, None, None, None

    parts = re.split(r"\s*[-–—]\s*", raw, maxsplit=1)
    since_raw = parts[0].strip() or None
    till_raw = parts[1].strip() if len(parts) > 1 else None

    since = _parse_month_year(since_raw) if since_raw else None
    till = _parse_month_year(till_raw) if till_raw else None

    msg = None
    if since_raw and since is None:
        msg = f"не распознано начало активности: {since_raw!r}"
    return since, since_raw, till, till_raw, msg


# --- соцсети -------------------------------------------------------------


def _tokens(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        for tok in re.split(r"[\s,;]+", (value or "").strip()):
            tok = tok.strip()
            if tok:
                out.append(tok)
    return out


def classify_socials(values: list[str]) -> dict[str, str | None]:
    """Разложить ссылки/хендлы на vk / telegram / facebook по содержимому."""
    result: dict[str, str | None] = {"vk": None, "telegram": None, "facebook": None}
    for tok in _tokens(values):
        low = tok.lower()
        if ("vk.com" in low or "vk.ru" in low or "m.vk.com" in low) and result["vk"] is None:
            result["vk"] = tok
        elif ("facebook.com" in low or "fb.com" in low) and result["facebook"] is None:
            result["facebook"] = tok
        elif result["telegram"] is None and ("t.me" in low or "telegram" in low or tok.startswith("@")):
            result["telegram"] = tok
    return result


def extract_emails(values: list[str]) -> tuple[str | None, str | None, str | None]:
    """(best_email, personal_email, message)."""
    best: str | None = None
    personal: str | None = None
    found_any = False
    has_text = any((v or "").strip() for v in values)
    for value in values:
        for match in _EMAIL.findall(value or ""):
            found_any = True
            email = match.strip().lower()
            if email.endswith("best-eu.org"):
                best = best or email
            else:
                personal = personal or email
    msg = None
    if has_text and not found_any:
        msg = "значение не похоже на email"
    return best, personal, msg


def parse_gender(raw: str) -> tuple[str | None, str | None]:
    raw = (raw or "").strip().lower()
    if not raw:
        return None, None
    if raw.startswith(("f", "ж")):
        return "female", None
    if raw.startswith(("m", "м")):
        return "male", None
    return None, f"неизвестный пол: {raw!r}"


# --- учёба ---------------------------------------------------------------

_GROUP_RE = re.compile(r"\d")


def classify_faculty_group(values: list[str]) -> tuple[str | None, str | None]:
    """Разделить «Факультет, группа» на текст факультета и код группы."""
    faculty: str | None = None
    group: str | None = None
    for value in values:
        value = (value or "").strip()
        if not value:
            continue
        digits = len(_GROUP_RE.findall(value))
        if digits >= 2 and group is None:
            group = value
        elif (_CYR.search(value) or _LAT.search(value)) and faculty is None:
            faculty = value
    return faculty, group


def extract_instagram(values: list[str]) -> str | None:
    for value in values:
        value = (value or "").strip()
        if value:
            return value.split()[0].lstrip("@") or None
    return None


_DORM_RE = re.compile(r"(общежити\w*|общага\w*|общ\.?\s*№?\s*\d+|dorm\w*)", re.IGNORECASE)


def extract_dormitory(address: str | None) -> str | None:
    if not address:
        return None
    for segment in re.split(r"[\n,;]", address):
        if _DORM_RE.search(segment):
            return segment.strip() or None
    return None
