"""Логирование сервиса.

Три настраиваемых приёмника:
- stdout контейнера   — все уровни (LOG_TO_CONSOLE);
- файл с ротацией     — все уровни (LOG_TO_FILE);
- markdown-файл       — только warning/error (LOG_TO_MD).

Использует structlog поверх stdlib logging (как в боте), поэтому все приёмники
получают одни и те же события.
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

from env import LoggerKeys


class MarkdownLogHandler(logging.Handler):
    """Дописывает warning/error в markdown-файл по одной строке-пункту.

    Файл пересоздаётся при инициализации процесса, поэтому содержит ошибки
    текущего запуска (для cron-режима — с момента старта контейнера).
    """

    def __init__(self, path: Path, level: int = logging.WARNING) -> None:
        super().__init__(level=level)
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        header = f"# members_sync — предупреждения и ошибки\n\n_старт: {datetime.now():%Y-%m-%d %H:%M:%S}_\n\n"
        self.path.write_text(header, encoding="utf-8")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
            line = f"- **{record.levelname}** `{ts}` `{record.name}` — {msg}\n"
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception:  # noqa: BLE001 - логгер не должен ронять приложение
            self.handleError(record)


def _shared_processors() -> list:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False, key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def setup_logging() -> None:
    level = getattr(logging, LoggerKeys.LOG_LEVEL, logging.DEBUG)

    structlog.configure(
        processors=[
            *_shared_processors(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=LoggerKeys.USE_COLORS_IN_CONSOLE, pad_level=True),
    )
    plain_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.KeyValueRenderer(
            key_order=["timestamp", "level", "logger", "event"],
            sort_keys=True,
        ),
    )
    # Для markdown берём только человекочитаемое сообщение (event), без служебных ключей.
    md_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.KeyValueRenderer(key_order=["event"]),
    )

    handlers: list[logging.Handler] = []

    if LoggerKeys.LOG_TO_CONSOLE:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(console_formatter)
        console.setLevel(level)
        handlers.append(console)

    if LoggerKeys.LOG_TO_FILE:
        log_file = Path(LoggerKeys.LOG_FILE_PATH)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LoggerKeys.LOG_FILE_MAX_SIZE,
            backupCount=LoggerKeys.LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(plain_formatter)
        file_handler.setLevel(level)
        handlers.append(file_handler)

    if LoggerKeys.LOG_TO_MD:
        md_level = getattr(logging, LoggerKeys.LOG_MD_LEVEL, logging.WARNING)
        md_handler = MarkdownLogHandler(Path(LoggerKeys.LOG_MD_PATH), level=md_level)
        md_handler.setFormatter(md_formatter)
        handlers.append(md_handler)

    root = logging.getLogger()
    root.handlers.clear()
    for handler in handlers:
        root.addHandler(handler)
    # Корневой уровень — минимальный из приёмников, чтобы markdown получал warning+.
    root.setLevel(min([h.level for h in handlers], default=level))

    # gspread/asyncio шумят на DEBUG — приглушим.
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
