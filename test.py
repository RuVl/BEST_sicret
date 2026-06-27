import json
from pprint import pprint

import gspread
from gspread.exceptions import SpreadsheetNotFound


def parse_besties(worksheet_id):
    gc = gspread.service_account("service_account.json")

    try:
        wks = gc.open_by_key(worksheet_id)
    except SpreadsheetNotFound:
        print("Worksheet not found")
        return
    except PermissionError:
        print("Permission error")

    pprint(wks)

    besties = set()
    wks

    s = next(
        filter(
            lambda w: w.title.lower().contains("database of members"), wks.worksheets()
        ),
        None,
    )
    if s is None:
        return besties

    print(wks.sheet1.title)
    print(s.col_values(1))
    print(s.col_values(2))
    return besties


if __name__ == "__main__":
    # SpreadsheetNotFound
    # besties = parse_besties('1K49LmaqXMNf08YDM2dI5ovL3QgshBjcGFXP4h3oNv3E')
    besties = parse_besties("1UC8XMksdtidiygiohpjObHmRWKJmCiNomVOXc8SrqlI")
    with open("test.json", "w", encoding="utf-8") as f:
        json.dump(besties, f, ensure_ascii=False, indent=4)
