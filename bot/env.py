from pathlib import Path
from typing import Final

import environ

# set casting, default value
env = environ.Env(
	DEBUG=(bool, False),
	LOG_FILE_MAX_SIZE=(int, 100 * 1024 * 1024),  # 100 MB
	LOG_FILE_BACKUP_COUNT=(int, 5),  # Keep 5 backup files
)


class TelegramKeys:
	API_TOKEN: Final[str] = env('TG_API_TOKEN')


class RedisKeys:
	HOST: Final[str] = env.str('REDIS_HOST', default='localhost')
	PORT: Final[str] = env.str('REDIS_PORT', default='6379')
	DATABASE: Final[str] = env.str('REDIS_DB', default='0')
	URL: Final[str] = env.str('REDIS_URL', default=f'redis://{HOST}:{PORT}/{DATABASE}')


class ProjectKeys:
	DEBUG: Final[bool] = env.bool('DEBUG')

	TEMPLATES_DIR: Final[Path] = env('TEMPLATES_DIR', default=Path('resources/templates/'))

	LOCALE_DIR: Final[Path] = env('LOCALE_DIR', default=Path('l10n/'))
	AVAILABLE_LOCALES: Final[list[str]] = env.list('AVAILABLE_LOCALES', default=['ru'])


class LoggerKeys:
	SHOW_DEBUG_LOGS: Final[bool] = env.bool('SHOW_DEBUG_LOGS', default=False)

	SHOW_DATETIME: Final[bool] = env.bool('SHOW_DATETIME', default=False)
	DATETIME_FORMAT: Final[str] = env.str('DATETIME_FORMAT', default='%Y-%m-%d %H:%M:%S')
	TIME_IN_UTC: Final[bool] = env.bool('TIME_IN_UTC', default=False)

	USE_COLORS_IN_CONSOLE: Final[bool] = env.bool('USE_COLORS_IN_CONSOLE', default=False)

	# File logging configuration
	LOG_TO_FILE: Final[bool] = env.bool('LOG_TO_FILE', default=True)
	LOG_FILE_PATH: Final[str] = env.str('LOG_FILE_PATH', default='logs/bot.log')
	LOG_FILE_MAX_SIZE: Final[int] = env.int('LOG_FILE_MAX_SIZE')
	LOG_FILE_BACKUP_COUNT: Final[int] = env.int('LOG_FILE_BACKUP_COUNT')
