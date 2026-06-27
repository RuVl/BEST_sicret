import csv
from datetime import date
from pathlib import Path

import pytest

from parsing.issues import IssueCollector
from parsing.member_builder import build
from sheets.column_mapper import resolve_columns
from sheets.record_reader import iterate_records
from sheets.spec import LAYOUT_A, spec_for_title

ROOT = Path(__file__).resolve().parents[2]

# Заголовок раскладки A (как в page1), сокращён до нужных колонок по позициям.
HEADER_A = [
    "",
    "ФИО",
    "Телефон",
    "Вконтакте,\nTelegram",
    "Your BEST gmail",
    "Status/field",
    "Birthday",
    "Начало активности (Набор)",
    "Angel",
    "Институт, группа",
    "Home address",
    "Local Involvement",
    "BEST events participated",
    "International involvement",
    "Instagram",
    "Пол",
]


def _parse_values(values, spec, title="Database of Members"):
    issues = IssueCollector()
    colmap = resolve_columns(values, spec, title, issues)
    members = [m for r in iterate_records(values, spec, colmap, title) if (m := build(r, spec, issues))]
    return members, issues, colmap


def test_synthetic_two_row_member():
    values = [
        HEADER_A,
        ["", "BOARD", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        [
            "1",
            "Иванова Анна Сергеевна",
            "89312988054",
            "https://vk.com/anna",
            "anna.ivanova@best-eu.org",
            "President of XVIII Board",
            "20.02.2004",
            "March 2024",
            "Ментор Имя",
            "ИПМЭиТ",
            "пр. Луначарского 1",
            "MO",
            "aGA'25",
            "coorg",
            "@anna_i",
            "Female",
        ],
        ["", "Ivanova Anna", "", "@anna_tg", "", "", "", "", "", "3733806/20102", "", "", "", "", "", ""],
    ]
    members, issues, colmap = _parse_values(values, LAYOUT_A)

    assert len(members) == 1
    m = members[0]
    assert m.full_name_ru == "Иванова Анна Сергеевна"
    assert m.full_name_en == "Ivanova Anna"
    assert m.best_email == "anna.ivanova@best-eu.org"
    assert m.identity_key == "anna.ivanova@best-eu.org"
    assert m.phone == "+79312988054"
    assert m.vk_url == "https://vk.com/anna"
    assert m.telegram == "@anna_tg"
    assert m.study_group == "3733806/20102"
    assert m.birthday == date(2004, 2, 20)
    assert m.active_since == date(2024, 3, 1)
    assert m.gender == "female"
    assert m.membership_category == "board"
    assert m.membership_status == "active"
    assert m.is_active is True
    assert m.source_row_start == 3 and m.source_row_end == 4
    # raw snapshot не теряет данные
    assert m.raw["cells"]["name"]["p"] == "Иванова Анна Сергеевна"
    assert not issues.errors


def test_identity_fallback_to_name_without_email():
    values = [
        HEADER_A,
        ["", "FULL MEMBERS", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        [
            "1",
            "Зайцева Юлианна",
            "89608574226",
            "https://vk.com/haheho",
            "",
            "",
            "18.01.2005",
            "March 2023",
            "",
            "ИСИ",
            "",
            "",
            "",
            "",
            "",
            "Female",
        ],
    ]
    members, _, _ = _parse_values(values, LAYOUT_A)
    assert len(members) == 1
    assert members[0].best_email is None
    assert members[0].identity_key == "зайцева юлианна"


def test_header_reordering_is_handled():
    # Меняем местами Birthday и Телефон — маппинг по заголовку должен это пережить.
    header = list(HEADER_A)
    header[2], header[6] = header[6], header[2]
    row = [
        "1",
        "Тест Тестов",
        "20.02.2004",
        "https://vk.com/t",
        "t@best-eu.org",
        "",
        "89312988054",
        "March 2024",
        "",
        "ИСИ",
        "",
        "",
        "",
        "",
        "",
        "Male",
    ]
    values = [header, ["", "BOARD", "", "", "", "", "", "", "", "", "", "", "", "", "", ""], row]
    members, _, _ = _parse_values(values, LAYOUT_A)
    assert members[0].birthday == date(2004, 2, 20)
    assert members[0].phone == "+79312988054"


def _load_csv(name: str):
    path = ROOT / name
    with path.open(encoding="utf-8") as f:
        return list(csv.reader(f))


@pytest.mark.skipif(not (ROOT / "page1.csv").exists(), reason="нет page1.csv")
def test_real_page1_smoke():
    values = _load_csv("page1.csv")
    members, issues, colmap = _parse_values(values, spec_for_title("Database of Members"))

    # Все ключевые колонки сопоставлены.
    for col in ("name", "email", "phone", "birthday", "social", "faculty_group"):
        assert col in colmap

    assert len(members) >= 40
    # Первая секция — BOARD.
    assert members[0].membership_category == "board"
    # У большинства активных есть корпоративная почта.
    with_best = [m for m in members if m.best_email]
    assert len(with_best) >= len(members) * 0.7
    # Идентичности уникальны в пределах листа на этих данных не гарантируются,
    # но критических ошибок парсинга быть не должно (кроме отсутствия идентичности).
    assert all(m.identity_key for m in members)


@pytest.mark.skipif(not (ROOT / "page3.csv").exists(), reason="нет page3.csv")
def test_real_page3_ex_members():
    values = _load_csv("page3.csv")
    members, _, _ = _parse_values(values, spec_for_title("Ex-members"))
    assert len(members) >= 40
    # Все на листе Ex-members имеют ex-статус.
    assert all(m.membership_status == "ex" for m in members)
