import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Импорты обработчиков
from handlers import menu
from handlers import speaking_club

# Токен бота
BOT_TOKEN = "8822263360:AAHLuQ9L5cR9fN5KpD_5AKR0gf_xps1DuKE"

async def main():
    logging.basicConfig(level=logging.INFO)
    
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(menu.router)
    dp.include_router(speaking_club.router)

    print("🤖 Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())