import pytest
from best_db.matching import normalize_telegram_handle


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@john_doe", "john_doe"),
        ("john_doe", "john_doe"),
        ("JohnDoe", "johndoe"),
        ("t.me/john_doe", "john_doe"),
        ("https://t.me/john_doe", "john_doe"),
        ("https://telegram.me/john_doe", "john_doe"),
        ("telegram: @john_doe", "john_doe"),
        ("tg://resolve?domain=john_doe", "john_doe"),
        ("  @John_Doe  ", "john_doe"),
        ("https://t.me/john_doe?start=ref", "john_doe"),
        ("@john_doe (рабочий)", "john_doe"),
    ],
)
def test_normalize_telegram_handle_ok(raw, expected):
    assert normalize_telegram_handle(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "@abc",  # короче 5 символов
        "https://t.me/+AbCdEf123",  # инвайт-ссылка, не username
        "просто текст без хэндла",
        "вконтакте.рф/id123",
    ],
)
def test_normalize_telegram_handle_none(raw):
    assert normalize_telegram_handle(raw) is None
