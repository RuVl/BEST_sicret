import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from structlog.typing import FilteringBoundLogger

from bot.config_reader import LogConfig, get_config, BotConfig
from bot.handlers import register_handlers
from bot.logs import get_structlog_config
from bot.middlewares import register_middlewares


async def main():
    # Init logging
    log_config: LogConfig = get_config(model=LogConfig)
    structlog.configure(**get_structlog_config(log_config))

    # Init bot
    bot_config: BotConfig = get_config(model=BotConfig)
    bot = Bot(
        token=bot_config.token.get_secret_value(),  # get token as secret, so it will be hidden in logs
        default=DefaultBotProperties(
            parse_mode=ParseMode.MARKDOWN_V2
        )
    )
    await bot.set_my_commands([
        BotCommand(command='start', description='Запуск бота'),
        BotCommand(command='create_document', description='Создать приказ')
    ])

    # Init dispatcher
    dp = Dispatcher()
    register_handlers(dp)
    register_middlewares(dp)

    logger: FilteringBoundLogger = structlog.get_logger()
    await logger.ainfo("Starting the bot...")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()  # Get only registered updates
        )
    finally:
        await bot.session.close()
        await logger.ainfo("Bot stopped.")


# Start bot
asyncio.run(main())