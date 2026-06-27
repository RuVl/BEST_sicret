import dataclasses
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pprint import pprint
from typing import Optional

import gspread


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)


@dataclass
class Person:
    department: Optional[str] = None
    number: Optional[str] = None
    full_name_ru: Optional[str] = None
    full_name_en: Optional[str] = None
    phone: Optional[str] = None
    vk_telegram1: Optional[str] = None
    vk_telegram2: Optional[str] = None
    email: Optional[str] = None
    status_field: Optional[str] = None
    birthday: Optional[date] = None
    start_working_date: Optional[date] = None
    boss_name: Optional[str] = None
    institute: Optional[str] = None
    group: Optional[str] = None
    address: Optional[str] = None
    local_involvement: Optional[str] = None
    events_participated: Optional[str] = None
    international_involvement: Optional[str] = None
    instagram: Optional[str] = None

    def __repr__(self):
        return f"Person({', '.join(f'{k}={v!r}' for k, v in asdict(self).items() if v is not None)})"


def parse_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None
    formats = [
        "%B %Y",  # March 2025
        "%d.%m.%Y",  # 01.03.2025
        "%m.%Y",  # 03.2025
        "%Y-%m-%d",  # 2025-03-01 (if any)
        "%d/%m/%Y",  # 01/03/2025
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            pass
    # Handle partial dates or other patterns if needed
    if re.match(r"^\d{4}$", date_str):  # Just year
        return datetime(int(date_str), 1, 1).date()
    return None


def normalize_phone(phone: str) -> Optional[str]:
    if not phone:
        return None
    # Remove non-digits
    phone = re.sub(r"\D", "", phone)
    # Russian phones: +7 or 8 -> +7
    if phone.startswith("8") and len(phone) == 11:
        phone = "7" + phone[1:]
    elif not phone.startswith("7") and len(phone) == 10:
        phone = "7" + phone
    if len(phone) == 11 and phone.startswith("7"):
        return "+" + phone
    return None  # Or return original if not matching


def get_cell(row: list, col: int) -> str:
    return row[col].strip() if len(row) > col else ""


def is_empty_row(row: list) -> bool:
    return all(cell.strip() == "" for cell in row)


def sync_employees_from_sheet(
    spreadsheet_id: str, sheet_name: str = "Database of Members"
) -> list[Person]:
    # Setup gspread client (assuming service account or oauth credentials are configured)
    gc = gspread.service_account("service_account.json")  # Or gspread.oauth()

    # Open the spreadsheet and sheet
    sh = gc.open_by_key(spreadsheet_id)
    worksheet = sh.worksheet(sheet_name)

    # Get all rows as list of lists
    rows = worksheet.get_all_values()

    # Skip header row
    if rows:
        rows = rows[1:]

    employees = []
    current_department: Optional[str] = None
    i = 0
    while i < len(rows):
        row = rows[i]

        # Check for end: three consecutive empty rows
        if (
            i + 2 < len(rows)
            and is_empty_row(row)
            and is_empty_row(rows[i + 1])
            and is_empty_row(rows[i + 2])
        ):
            break

        # Skip single empty rows
        if is_empty_row(row):
            i += 1
            continue

        # Department separator: column 1 (index 1) has name, column 0 (index 0) is not a number
        col0 = get_cell(row, 0)
        col1 = get_cell(row, 1)
        if (not col0 or not col0.isdigit()) and col1:
            current_department = col1
            i += 1
            continue

        # Employee: expect two rows
        if i + 1 >= len(rows) or is_empty_row(rows[i + 1]):
            # Incomplete entry, skip or log error
            i += 1
            continue

        row1 = row
        row2 = rows[i + 1]

        # Parse fields from row1
        number = get_cell(row1, 0) or None
        full_name_ru = get_cell(row1, 1) or None
        phone = normalize_phone(get_cell(row1, 2))
        vk_telegram1 = get_cell(row1, 3) or None
        email = get_cell(row1, 4) or None
        status_field = get_cell(row1, 5) or None
        birthday = parse_date(get_cell(row1, 6))
        start_working_date = parse_date(get_cell(row1, 7))
        boss_name = get_cell(row1, 8) or None
        institute = get_cell(row1, 9) or None
        address = get_cell(row1, 10) or None
        local_involvement = get_cell(row1, 11) or None
        events_participated = get_cell(row1, 12) or None
        international_involvement = get_cell(row1, 13) or None
        instagram = get_cell(row1, 14) or None

        # Parse fields from row2
        full_name_en = get_cell(row2, 1) or None
        vk_telegram2 = get_cell(row2, 3) or None
        group = get_cell(row2, 9) or None  # Group in column 9 of row2

        # Create Person
        person = Person(
            department=current_department,
            number=number,
            full_name_ru=full_name_ru,
            full_name_en=full_name_en,
            phone=phone,
            vk_telegram1=vk_telegram1,
            vk_telegram2=vk_telegram2,
            email=email,
            status_field=status_field,
            birthday=birthday,
            start_working_date=start_working_date,
            boss_name=boss_name,
            institute=institute,
            group=group,
            address=address,
            local_involvement=local_involvement,
            events_participated=events_participated,
            international_involvement=international_involvement,
            instagram=instagram,
        )

        employees.append(person)

        # Advance by 2 rows
        i += 2

    # Output to console
    print("Parsed employees:")
    for idx, emp in enumerate(employees, 1):
        print(f"\nEmployee {idx}:")
        pprint(asdict(emp))

    return employees


# Usage example:
employees = sync_employees_from_sheet("1K49LmaqXMNf08YDM2dI5ovL3QgshBjcGFXP4h3oNv3E")
with open("test2.json", "w", encoding="utf-8") as f:
    json.dump(employees, f, ensure_ascii=False, indent=4, cls=EnhancedJSONEncoder)
