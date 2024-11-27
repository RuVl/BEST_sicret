import logging
from json import dumps

import structlog
from structlog import WriteLoggerFactory

from bot.config_reader import LogConfig, LogRenderer


def get_structlog_config(log_config: LogConfig) -> dict:
    """
    Get config for a structlog
    :param log_config: LogConfig object with log parameters
    :return: dict with structlog config
    """

    # Show debug level logs?
    if log_config.show_debug_logs is True:
        min_level = logging.DEBUG
    else:
        min_level = logging.INFO

    return {
        "processors": get_processors(log_config),
        "cache_logger_on_first_use": True,
        "wrapper_class": structlog.make_filtering_bound_logger(min_level),
        "logger_factory": WriteLoggerFactory()
    }


def get_processors(log_config: LogConfig) -> list:
    """
    Returns processors list for structlog
    :param log_config: LogConfig object with log parameters
    :return: processors list for structlog
    """

    def custom_json_serializer(data, *args, **kwargs):
        """
        JSON-objects custom serializer
        """
        result = dict()

        if log_config.show_datetime is True:
            result["timestamp"] = data.pop("timestamp")

        # Other two keys goes in this order
        for key in ("level", "event"):
            if key in data:
                result[key] = data.pop(key)

        # Remaining keys will be printed "as is" (usually in alphabet order)
        result.update(**data)
        return dumps(result, default=str)

    processors = []

    # In some cases, there is no need to print a timestamp,
    # because it is already added by an upstream service, such as systemd
    if log_config.show_datetime is True:
        processors.append(structlog.processors.TimeStamper(
            fmt=log_config.datetime_format,
            utc=log_config.time_in_utc
        ))

    # Always add a log level
    processors.append(structlog.processors.add_log_level)

    match log_config.renderer:
        case LogRenderer.JSON:
            processors.append(structlog.processors.JSONRenderer(serializer=custom_json_serializer))
        case LogRenderer.CONSOLE:
            processors.append(structlog.dev.ConsoleRenderer(
                colors=log_config.use_colors_in_console,
                pad_level=True,
            ))

    return processors
