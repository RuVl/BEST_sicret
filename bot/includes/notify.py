"""Сообщение человеку из фоновой задачи или CLI: недоставка не должна ронять вызывающего."""

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from structlog.typing import FilteringBoundLogger

logger: FilteringBoundLogger = structlog.get_logger("notify")


async def notify(bot: Bot, chat_id: int, text: str) -> bool:
    """Отправить сообщение; человек мог заблокировать бота. ``True`` - сообщение ушло."""
    if not chat_id:
        return False
    try:
        await bot.send_message(chat_id, text)
    except TelegramAPIError as exc:
        await logger.awarning("notify-failed", chat_id=chat_id, error=str(exc))
        return False
    return True
