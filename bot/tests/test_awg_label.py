"""Названия устройств и экранирование MarkdownV2 для них."""

import pytest

from includes.awg import MAX_DEVICE_LABEL_LEN, DeviceLabelError, normalize_device_label
from utils import escape_mdv2


class TestEscapeBackslash:
    @pytest.mark.parametrize(
        ("text", "escaped"),
        [
            ("PC\\-1", "PC\\\\\\-1"),  # слэш и дефис - оба экранированы
            ("Ноут\\", "Ноут\\\\"),  # хвостовой слэш не съест закрывающую звёздочку
            ("a.b", "a\\.b"),
        ],
    )
    def test_backslash_escaped(self, text, escaped):
        assert escape_mdv2(text) == escaped

    def test_none_stays_none(self):
        assert escape_mdv2(None) is None


class TestDeviceLabel:
    @pytest.mark.parametrize("label", ["👨‍💻 Работа", "🏴󠁧󠁢󠁳󠁣󠁴󠁿 ноут", "Телефон ❤️", "PC\\-1"])
    def test_emoji_and_symbols_accepted(self, label):
        assert normalize_device_label(label) == label

    @pytest.mark.parametrize(
        ("value", "problem"),
        [
            ("   ", "empty"),
            ("\u200d\u200d", "empty"),  # одни невидимые соединители
            ("\u200d \u200c", "empty"),
            ("a" * (MAX_DEVICE_LABEL_LEN + 1), "too-long"),
            ("tab\u0007bell", "bad-chars"),
            ("скрытый\u200bпробел", "bad-chars"),
        ],
    )
    def test_problem_is_named(self, value, problem):
        with pytest.raises(DeviceLabelError) as error:
            normalize_device_label(value)
        assert error.value.problem == problem

    def test_limit_matches_db_column(self):
        assert MAX_DEVICE_LABEL_LEN == 32
