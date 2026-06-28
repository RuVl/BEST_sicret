from datetime import date

import pytest

from parsing import fields as F
from parsing.normalizers import (
    classify_faculty_group,
    classify_name,
    classify_socials,
    extract_emails,
    normalize_identity_name,
    normalize_phone,
    parse_active_period,
    parse_date,
    parse_gender,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20.02.2004", date(2004, 2, 20)),  # d.m.y
        ("8/30/1990", date(1990, 8, 30)),  # американский m/d/y
        ("11.16.1982", date(1982, 11, 16)),  # m.d.y (day > 12)
        ("27.05.93", date(1993, 5, 27)),  # 2-значный год
        ("4.11.2006", date(2006, 11, 4)),  # неоднозначно → европейский d.m
        ("3/1/2018 0:00:00", date(2018, 1, 3)),  # дата-время
    ],
)
def test_parse_date_ok(raw, expected):
    value, msg = parse_date(raw)
    assert value == expected
    assert msg is None


def test_parse_date_bad():
    value, msg = parse_date("не дата")
    assert value is None
    assert msg


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("89312988054", "+79312988054"),
        ("+7 (905) 855-66-44", "+79058556644"),
        ("8 (967) 550-22-11", "+79675502211"),
        ("79819598702", "+79819598702"),
        # Два номера в одной ячейке через \n — берём первый валидный, а не склейку.
        ("89219185707\n89215384144 (Whats App)", "+79219185707"),
        # Иностранные номера в международном формате (BEST — международная организация).
        ("+36 303 82 77 09", "+36303827709"),
        # Международный префикс 00 вместо «+».
        ("007 925 227 29 24", "+79252272924"),
    ],
)
def test_normalize_phone_ok(raw, expected):
    phone, raw_kept, msg = normalize_phone(raw)
    assert phone == expected
    assert raw_kept == raw
    assert msg is None


@pytest.mark.parametrize(
    "raw",
    [
        "звоните в вк",
        # 12 цифр — на одну длиннее российского номера (опечатка), не «дочиняем».
        "895127925420",
        "895335271440",
        # 11 цифр без «+» и не под российское правило — страну не угадываем.
        "32485939831",
    ],
)
def test_normalize_phone_garbage(raw):
    phone, raw_kept, msg = normalize_phone(raw)
    assert phone is None
    assert raw_kept == raw or raw_kept is None
    assert msg


def test_classify_name_swapped_rows():
    # Русское имя может оказаться во второй строке — должно всё равно попасть в ru.
    ru, en = classify_name(["Fedosimova Alexandra", "Федосимова Александра"])
    assert ru == "Федосимова Александра"
    assert en == "Fedosimova Alexandra"


def test_classify_socials():
    socials = classify_socials(["https://vk.com/golubech", "@Xandrals"])
    assert socials["vk"] == "https://vk.com/golubech"
    assert socials["telegram"] == "@Xandrals"
    assert socials["facebook"] is None


def test_classify_socials_facebook():
    socials = classify_socials(["t.me/lissk0", "https://www.facebook.com/x"])
    assert socials["telegram"] == "t.me/lissk0"
    assert socials["facebook"] == "https://www.facebook.com/x"


def test_extract_emails_best_vs_personal():
    best, personal, msg = extract_emails(["alexandra.fedosimova@best-eu.org"])
    assert best == "alexandra.fedosimova@best-eu.org"
    assert personal is None
    assert msg is None

    best, personal, _ = extract_emails(["someone@gmail.com"])
    assert best is None
    assert personal == "someone@gmail.com"


def test_extract_emails_not_email():
    best, personal, msg = extract_emails(["https://vk.com/x"])
    assert best is None and personal is None
    assert msg


@pytest.mark.parametrize(
    ("raw", "since", "till"),
    [
        ("March 2024", date(2024, 3, 1), None),
        ("March 2015 - May 2018", date(2015, 3, 1), date(2018, 5, 1)),
        ("Sep 22'", date(2022, 9, 1), None),
    ],
)
def test_parse_active_period(raw, since, till):
    s, _, t, _, _ = parse_active_period(raw)
    assert s == since
    assert t == till


def test_classify_faculty_group():
    faculty, group = classify_faculty_group(["ИПМЭиТ", "3733806/20102"])
    assert faculty == "ИПМЭиТ"
    assert group == "3733806/20102"


def test_parse_gender():
    assert parse_gender("Female")[0] == "female"
    assert parse_gender("Male")[0] == "male"
    assert parse_gender("")[0] is None


def test_normalize_identity_name():
    assert normalize_identity_name("  Фёдор   Иванов ") == "федор иванов"


@pytest.mark.parametrize(
    ("section", "expected"),
    [
        ("BOARD", ("board", "active")),
        ("FULL MEMBERS", ("full_member", "active")),
        ("ALUMNI", ("alumni", "alumni")),
        ("EX-BABY MEMBERS", ("ex_baby_member", "ex")),
        ("EX-something-new", ("ex_member", "ex")),  # эвристика
    ],
)
def test_classify_section(section, expected):
    assert F.classify_section(section, ("full_member", "active")) == expected
