from datetime import date

from parsing.issues import IssueCollector
from parsing.member_builder import build
from sheets.column_mapper import resolve_columns
from sheets.record_reader import iterate_records
from sheets.spec import LAYOUT_A, LAYOUT_B, spec_for_title

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
    assert m.is_active is True
    assert m.is_excluded is False
    assert m.source_row_start == 3 and m.source_row_end == 4
    # raw snapshot не теряет данные
    assert m.raw["cells"]["name"]["p"] == "Иванова Анна Сергеевна"
    assert not issues.errors


def test_name_only_secondary_row_not_treated_as_section():
    # Регрессия: вторая строка участника, где заполнено только имя транслитом,
    # раньше матчила эвристику секции и протекала в source_section следующих людей.
    def row(num, name, email):
        return [num, name, "89312988054", email, "", "", "", "", "", "", "", "", "", "", "", ""]

    values = [
        HEADER_B,
        ["", "ALUMNI", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        row("1", "Колесникович Максим", "maxim@best-eu.org"),
        ["", "Kolesnikovich Maxim", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        row("2", "Зеленецкий Илья", "ilia@best-eu.org"),
    ]
    members, _, _ = _parse_values(values, LAYOUT_B, title="Alumni+Former")

    assert len(members) == 2
    assert members[0].full_name_en == "Kolesnikovich Maxim"
    assert members[0].source_section == "ALUMNI"
    assert members[1].source_section == "ALUMNI"
    assert members[1].membership_category == "alumni"


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


# Заголовок раскладки B (Alumni…/Ex-members), порядок колонок по fallback-индексам spec.
HEADER_B = [
    "",
    "ФИО",
    "Телефон",
    "Your BEST gmail",
    "Status/field",
    "Birthday",
    "Active in BEST",
    "Angel",
    "Институт, группа",
    "Вконтакте,\nFacebook",
    "Local Involvement",
    "International involvement",
    "BEST events participated",
    "Home address",
    "Место работы",
    "Instagram",
]


def test_synthetic_page_with_many_members():
    # Несколько участников под секцией BOARD — массовый разбор листа раскладки A
    # (замена дымового теста на боевом page1.csv).
    def row(num, name, email):
        return [
            num,
            name,
            "89312988054",
            "https://vk.com/x",
            email,
            "President",
            "20.02.2004",
            "March 2024",
            "",
            "ИСИ",
            "",
            "",
            "",
            "",
            "",
            "Female",
        ]

    values = [
        HEADER_A,
        ["", "BOARD", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        row("1", "Иванова Анна", "anna@best-eu.org"),
        row("2", "Петрова Мария", "maria@best-eu.org"),
        row("3", "Сидорова Ольга", ""),  # без корпоративной почты → идентичность по ФИО
    ]
    members, issues, colmap = _parse_values(values, LAYOUT_A)

    # Все ключевые колонки сопоставлены.
    for col in ("name", "email", "phone", "birthday", "social", "faculty_group"):
        assert col in colmap
    assert len(members) == 3
    assert members[0].membership_category == "board"
    assert all(m.identity_key for m in members)
    # У большинства есть корпоративная почта.
    with_best = [m for m in members if m.best_email]
    assert len(with_best) >= len(members) * 0.6
    assert not issues.errors


def test_synthetic_ex_members_status():
    # Лист Ex-members: записи без секции получают ex-статус по умолчанию из spec
    # (замена дымового теста на боевом page3.csv).
    def row(num, name, email):
        return [
            num,
            name,
            "89312988054",
            email,
            "",
            "20.02.2004",
            "March 2015 - May 2018",
            "",
            "ИСИ",
            "https://vk.com/x",
            "",
            "",
            "",
            "",
            "ООО Рога и Копыта",
            "",
        ]

    values = [
        HEADER_B,
        row("1", "Иванова Анна", "anna@best-eu.org"),
        row("2", "Петрова Мария", "maria@best-eu.org"),
    ]
    members, _, _ = _parse_values(values, spec_for_title("Ex-members"), title="Ex-members")

    assert len(members) == 2
    assert all(m.membership_category == "ex_member" for m in members)
    assert all(m.is_excluded for m in members)
    assert all(not m.is_active for m in members)
