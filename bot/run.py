import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram_dialog.tools import render_transitions
from structlog.typing import FilteringBoundLogger

from handlers import register_handlers
from middlewares import register_middlewares
from env import TelegramKeys, ProjectKeys
from includes import setup_logging, get_storage, PickleRedisStorage


async def main():
	# Init logging
	setup_logging()

	# Init bot
	bot = Bot(
		token=TelegramKeys.API_TOKEN,
		default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
	)
	await bot.set_my_commands([
		BotCommand(command='start', description='Запуск бота'),
		BotCommand(command='create_document', description='Создать приказ')
	])

	# Get storage with proper configuration for dialogs
	storage = get_storage(cls=PickleRedisStorage, with_destiny=True)

	# Init dispatcher
	dp = Dispatcher(storage=storage)

	# Register handlers and middlewares
	register_handlers(dp)
	register_middlewares(dp)

	# Render dialogs preview
	if ProjectKeys.DEBUG:
		render_transitions(dp)

	# Start bot
	logger: FilteringBoundLogger = structlog.get_logger()
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
