import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from structlog.typing import FilteringBoundLogger

from env import TelegramKeys, ProjectKeys, RedisKeys
from handlers import register_handlers
from includes import setup_logging, get_redis_storage, PickleRedisStorage
from middlewares import register_middlewares


async def main():
    # Init logging
    setup_logging()
    logger: FilteringBoundLogger = structlog.get_logger()

    # Init bot
    bot = Bot(
        token=TelegramKeys.API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
    )
    await bot.set_my_commands([
        BotCommand(command='start', description='Запуск бота'),
        BotCommand(command='create_document', description='Создать приказ'),
        BotCommand(command='create_equipment_apply', description='Создать заявку по стаффу'),
        BotCommand(command='add_equipment', description='Добавить имущество')
    ])

    # Get storage with proper configuration for dialogs
    if RedisKeys.USE_REDIS:
        storage = get_redis_storage(cls=PickleRedisStorage, with_destiny=True)
    else:
        storage = MemoryStorage()
        if not ProjectKeys.DEBUG:
            logger.warning('You should use RedisStorage in production!')

    # Init dispatcher
    dp = Dispatcher(storage=storage)

    # Register handlers and middlewares
    register_middlewares(dp)
    register_handlers(dp)

    # Start bot
    await logger.ainfo(f"Starting the bot (id={bot.id})...")

    try:
        await dp.start_polling(
            bot,
            skip_updates=ProjectKeys.DEBUG,  # skip updates if debug
            allowed_updates=dp.resolve_used_update_types()  # Get only registered updates
        )
    finally:
        await bot.session.close()
        await logger.ainfo("Bot stopped.")


# Start bot
if __name__ == '__main__':
    asyncio.run(main())
