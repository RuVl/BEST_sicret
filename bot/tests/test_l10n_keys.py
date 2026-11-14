"""Проверки всех ключей локализации: новый ключ попадает под них без правки теста.

Fluent прячет ошибки молча: нераспарсенный кусок ``.ftl`` становится ``Junk`` и выбрасывается
(так обрывается сообщение на пустой строке или на строке, начинающейся с ``*``), а ``format_value``
вместо текста отдаёт имя ключа. Поэтому файлы разбираем сами и рендерим через ``FluentBundle``,
который возвращает ошибки, а не глотает их.

Экранирование зависит от того, куда уходит текст, и это видно по суффиксу ключа:

- без суффикса - сообщение с ``parse_mode=MarkdownV2``, спецсимволы обязаны быть экранированы;
- ``-btn`` - подпись кнопки, ``-url`` - ссылка кнопки, ``-alert`` - ответ на callback,
  ``-part`` - кусок, который код экранирует сам при вставке в сообщение. Telegram показывает
  их как есть, поэтому экранирования в них быть не должно.
"""

import ast as py_ast
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fluent.runtime import FluentBundle
from fluent.syntax import FluentParser, ast, visitor

from env import settings
from includes import get_fluent_localization

PLAIN_SUFFIXES = ("-btn", "-url", "-alert", "-part")

BOT_DIR = Path(__file__).resolve().parents[1]
LOCALE_DIR = BOT_DIR / settings.project.LOCALE_DIR
LOCALES = settings.project.AVAILABLE_LOCALES


# === Разбор .ftl ===


def _parse(path: Path) -> ast.Resource:
    return FluentParser().parse(path.read_text(encoding="utf-8"))


FTL_FILES = {locale: sorted((LOCALE_DIR / locale).rglob("*.ftl")) for locale in LOCALES}
RESOURCES = {path: _parse(path) for paths in FTL_FILES.values() for path in paths}
MESSAGES = {
    locale: [entry for path in paths for entry in RESOURCES[path].body if isinstance(entry, ast.Message)]
    for locale, paths in FTL_FILES.items()
}
ALL_MESSAGES = [(locale, message) for locale, messages in MESSAGES.items() for message in messages]
MARKDOWN_MESSAGES = [(lc, msg) for lc, msg in ALL_MESSAGES if not msg.id.name.endswith(PLAIN_SUFFIXES)]
PLAIN_MESSAGES = [(lc, msg) for lc, msg in ALL_MESSAGES if msg.id.name.endswith(PLAIN_SUFFIXES)]
BUTTON_MESSAGES = [(lc, msg) for lc, msg in ALL_MESSAGES if msg.id.name.endswith("-btn")]
URL_MESSAGES = [(lc, msg) for lc, msg in ALL_MESSAGES if msg.id.name.endswith("-url")]


def _ids(cases: list[tuple[str, ast.Message]]) -> list[str]:
    return [f"{locale}:{message.id.name}" for locale, message in cases]


class _Variables(visitor.Visitor):
    def __init__(self) -> None:
        super().__init__()
        self.names: set[str] = set()

    def visit_VariableReference(self, node: ast.VariableReference) -> None:
        self.names.add(node.id.name)


def _dummy_args(message: ast.Message) -> dict[str, int]:
    """Аргументы берём из самого шаблона - словарь значений руками вести не нужно.

    Число подходит и для подстановки, и для селекторов множественного числа, а спецсимволов
    в нём нет: экранирование настоящих значений - забота геттеров, не шаблона.
    """
    variables = _Variables()
    variables.visit(message)
    return dict.fromkeys(variables.names, 1)


def _bundle(locale: str) -> FluentBundle:
    bundle = FluentBundle([locale], use_isolating=False)
    for path in FTL_FILES[locale]:
        bundle.add_resource(RESOURCES[path])
    return bundle


BUNDLES = {locale: _bundle(locale) for locale in LOCALES}


def _render(locale: str, message: ast.Message) -> str:
    bundle = BUNDLES[locale]
    text, errors = bundle.format_pattern(bundle.get_message(message.id.name).value, _dummy_args(message))
    assert not errors, errors
    return text


# === Валидация MarkdownV2 ===

# Telegram разрешает экранировать любой символ с кодом 1-126, не только спецсимволы.
_MD_ESCAPED = re.compile(r"\\[\x01-\x7e]")
_MD_CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
_MD_LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
_MD_QUOTE = re.compile(r"^\*{0,2}>", re.M)
_MD_PAIRED = ("||", "*", "_", "~")
_MD_SPECIAL = re.compile(r"[\\`\[\]()>#+\-=|{}.!]")


def _markdown_v2_problems(text: str) -> list[str]:
    """Упрощённый разбор MarkdownV2: разметку снимаем, неэкранированные спецсимволы - ошибка."""
    text = _MD_ESCAPED.sub("", text)
    text = _MD_CODE.sub("", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _MD_QUOTE.sub("", text)

    problems = []
    for marker in _MD_PAIRED:
        if text.count(marker) % 2:
            problems.append(f"непарный {marker!r}")
        text = text.replace(marker, "")
    problems.extend(f"неэкранированный {char!r}" for char in sorted(set(_MD_SPECIAL.findall(text))))
    return problems


# === Структура файлов ===


@pytest.mark.parametrize("path", list(RESOURCES), ids=lambda p: str(p.relative_to(LOCALE_DIR)))
def test_ftl_has_no_junk(path):
    junk = [entry.content.strip() for entry in RESOURCES[path].body if isinstance(entry, ast.Junk)]

    assert not junk, f"Fluent не разобрал и выбросит: {junk}"


@pytest.mark.parametrize("locale", LOCALES)
def test_keys_are_unique(locale):
    # Файлы грузятся в случайном порядке, поэтому при дубле значение ключа зависело бы от запуска.
    counts = Counter(message.id.name for message in MESSAGES[locale])

    assert not [key for key, count in counts.items() if count > 1]


@pytest.mark.parametrize(("locale", "message"), ALL_MESSAGES, ids=_ids(ALL_MESSAGES))
def test_message_has_value_without_attributes(locale, message):
    # Строка вида «.name = …» внутри шаблона стала бы атрибутом и пропала бы из текста.
    assert message.value is not None
    assert not message.attributes


@pytest.mark.parametrize(("locale", "message"), ALL_MESSAGES, ids=_ids(ALL_MESSAGES))
def test_message_renders_without_errors(locale, message):
    assert _render(locale, message).strip()


@pytest.mark.parametrize(("locale", "message"), ALL_MESSAGES, ids=_ids(ALL_MESSAGES))
def test_loader_resolves_message(locale, message):
    """Боевой загрузчик видит ключ: файл подхватился и ключ не подменяется своим именем."""
    l10n = get_fluent_localization()
    key = message.id.name

    assert l10n.format_value(key, args=_dummy_args(message)) != key


# === Экранирование по суффиксу ===


@pytest.mark.parametrize(("locale", "message"), MARKDOWN_MESSAGES, ids=_ids(MARKDOWN_MESSAGES))
def test_markdown_keys_are_valid_markdown_v2(locale, message):
    problems = _markdown_v2_problems(_render(locale, message))

    assert not problems, f"{problems}; если это кнопка или алерт - нужен суффикс из {PLAIN_SUFFIXES}"


@pytest.mark.parametrize(("locale", "message"), PLAIN_MESSAGES, ids=_ids(PLAIN_MESSAGES))
def test_plain_keys_have_no_escapes(locale, message):
    assert "\\" not in _render(locale, message)


@pytest.mark.parametrize(("locale", "message"), BUTTON_MESSAGES, ids=_ids(BUTTON_MESSAGES))
def test_button_keys_are_single_line(locale, message):
    assert "\n" not in _render(locale, message)


@pytest.mark.parametrize(("locale", "message"), URL_MESSAGES, ids=_ids(URL_MESSAGES))
def test_url_keys_are_urls(locale, message):
    url = urlparse(_render(locale, message))

    assert url.scheme in ("http", "https", "tg")
    assert url.netloc


def test_markdown_v2_checker_catches_mistakes():
    """Сам разборщик: разметку пропускает, ошибки ловит."""
    assert not _markdown_v2_problems(r"*Жирный* _курсив_ `код.` [ссылка](https://a.b/c) \- точка\.")
    assert _markdown_v2_problems("Точка.")
    assert _markdown_v2_problems("*непарная звёздочка")
    assert _markdown_v2_problems("скобки (без экранирования)")
    assert not _markdown_v2_problems(r"двоеточие\: можно экранировать")


# === Ключи из кода ===

_LOCALIZATION_CALLS = ("format_value", "L10nFormat")


def _key_patterns(node: py_ast.expr) -> list[str]:
    """Регулярка ключа из литерала; f-строка превращается в шаблон, тернарник - в обе ветки."""
    if isinstance(node, py_ast.Constant) and isinstance(node.value, str):
        return [re.escape(node.value)]
    if isinstance(node, py_ast.IfExp):
        return _key_patterns(node.body) + _key_patterns(node.orelse)
    if isinstance(node, py_ast.JoinedStr):
        return [
            "".join(
                re.escape(part.value) if isinstance(part, py_ast.Constant) else "[a-z0-9-]+" for part in node.values
            )
        ]
    # Ключ из переменной статически не узнать - такие вызовы не проверяем.
    return []


def _code_keys() -> list[tuple[str, str]]:
    found = []
    for path in sorted(BOT_DIR.rglob("*.py")):
        relative = path.relative_to(BOT_DIR)
        if relative.parts[0] in (".venv", "tests"):
            continue
        for node in py_ast.walk(py_ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, py_ast.Call) or not node.args:
                continue
            func = node.func
            name = func.attr if isinstance(func, py_ast.Attribute) else getattr(func, "id", None)
            if name in _LOCALIZATION_CALLS:
                found += [(f"{relative}:{node.lineno}", pattern) for pattern in _key_patterns(node.args[0])]
    return found


CODE_KEYS = _code_keys()


@pytest.mark.parametrize(("location", "pattern"), CODE_KEYS, ids=[location for location, _ in CODE_KEYS])
@pytest.mark.parametrize("locale", LOCALES)
def test_code_keys_exist(locale, location, pattern):
    keys = {message.id.name for message in MESSAGES[locale]}

    assert any(re.fullmatch(pattern, key) for key in keys), f"{location}: ключа {pattern!r} нет в {locale}"
