import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from database3 import (
    create_tables,
    ensure_appointments_columns,
    seed_data,
    seed_service_specialists,
    seed_schedule,
)
from handlers3 import register_handlers

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found in .env")
ADMIN_IDS = {1071651315}

async def main():
    logging.basicConfig(level=logging.INFO)

    # База
    create_tables()
    ensure_appointments_columns()
    seed_data()
    seed_service_specialists()
    seed_schedule()

    dp = Dispatcher(storage=MemoryStorage())
    register_handlers(dp)

    # ✅ ВАЖНО: Bot в контекстном менеджере
    async with Bot(token=os.getenv("BOT_TOKEN")) as bot:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())