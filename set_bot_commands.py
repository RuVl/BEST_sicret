from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault
import asyncio

API_TOKEN = "8774748698:AAE7DfRvzT1kBJ_vKXdnbKofGBA2vkHfcn8"  # Замените на ваш токен

async def main():
    bot = Bot(token=API_TOKEN)
    await bot.set_my_commands([
        BotCommand(command='start', description='Запуск бота'),
        BotCommand(command='create_document', description='Создать приказ'),
        BotCommand(command='create_requisites_apply', description='Создать заявку на рефанд')
    ], scope=BotCommandScopeDefault())
    print("Команды успешно установлены!")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
