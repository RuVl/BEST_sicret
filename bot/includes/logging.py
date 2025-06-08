import logging
import sys
from pathlib import Path

import structlog

from env import LoggerKeys, ProjectKeys


class StructlogOnlyFilter(logging.Filter):
	"""
	Пропускает только записи логов, созданные через structlog.
	"""

	def filter(self, record: logging.LogRecord) -> bool:
		# Проверяем, является ли основной 'msg' записи словарем.
		# Это специфично для того, как structlog.stdlib передает данные.
		is_structlog_msg = isinstance(record.msg, dict)
		return is_structlog_msg


# noinspection SpellCheckingInspection
def setup_logging():
	"""
	Настраивает structlog для вывода в консоль (цветной) и файл (без цвета).
	"""
	min_level = logging.DEBUG if LoggerKeys.SHOW_DEBUG_LOGS else logging.INFO

	# --- Шаг 1: Определяем ОБЩИЕ процессоры (без финального рендеринга) ---
	shared_processors = get_shared_processors()

	# --- Шаг 2: Конфигурируем structlog для интеграции с logging ---
	structlog.configure(
		processors=[
			*shared_processors,
			# Этот процессор ВАЖЕН для интеграции: он подготавливает event_dict для форматтеров logging. Он должен быть ПОСЛЕДНИМ в этой цепочке.
			structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
		],
		logger_factory=structlog.stdlib.LoggerFactory(),
		wrapper_class=structlog.stdlib.BoundLogger,
		cache_logger_on_first_use=True,
	)

	# --- Шаг 3: Создаем форматтеры logging с разными финальными процессорами structlog ---
	console_formatter = structlog.stdlib.ProcessorFormatter(
		processor=structlog.dev.ConsoleRenderer(
			colors=LoggerKeys.USE_COLORS_IN_CONSOLE,
			pad_level=True
		),
		# foreign_pre_chain=shared_processors,
	)

	if not ProjectKeys.DEBUG:
		file_formatter = structlog.stdlib.ProcessorFormatter(
			processor=structlog.processors.KeyValueRenderer(
				key_order=['timestamp', 'level', 'logger', 'event'],
				sort_keys=True
			),
			# foreign_pre_chain=shared_processors,
		)

	# --- Шаг 4: Создаем и настраиваем обработчики (Handlers) ---
	structlog_filter = StructlogOnlyFilter()

	console_handler = logging.StreamHandler(sys.stdout)
	console_handler.setFormatter(console_formatter)
	if not ProjectKeys.DEBUG:
		console_handler.addFilter(structlog_filter)

	if not ProjectKeys.DEBUG:
		logger_file = Path(LoggerKeys.LOG_FILE_PATH)
		logger_file.parent.mkdir(parents=True, exist_ok=True)

		file_handler = logging.FileHandler(logger_file, mode='a', encoding='utf-8')
		file_handler.setFormatter(file_formatter)

	# --- Шаг 5: Настройка корневого логгера ---
	root_logger = logging.getLogger()
	root_logger.handlers.clear()
	root_logger.addHandler(console_handler)

	if not ProjectKeys.DEBUG:
		root_logger.addHandler(file_handler)

	root_logger.setLevel(min_level)


# noinspection SpellCheckingInspection
def get_shared_processors() -> list:
	"""
	Возвращает ОБЩИЙ список процессоров для structlog (БЕЗ финального рендеринга).
	Эти процессоры выполняются до передачи форматтерам logging.
	:return: Список общих процессоров
	"""
	processors = [
		structlog.contextvars.merge_contextvars,
		structlog.stdlib.add_logger_name,
		structlog.stdlib.add_log_level,
		structlog.stdlib.ExtraAdder(),
	]

	if LoggerKeys.SHOW_DATETIME:
		processors.append(structlog.processors.TimeStamper(
			fmt=LoggerKeys.DATETIME_FORMAT if LoggerKeys.DATETIME_FORMAT != "iso" else None,  # None использует ISO 8601 по умолчанию
			utc=LoggerKeys.TIME_IN_UTC,
			key="timestamp"  # Явно указываем ключ, полезно для рендереров
		))

	# Нет add_log_level, т.к. structlog.stdlib.add_log_level добавляется автоматически при интеграции с logging (в structlog.configure)

	processors.extend([
		structlog.processors.StackInfoRenderer(),
		structlog.processors.format_exc_info,
	])

	return processors
