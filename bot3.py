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

TOKEN = "7789519280:AAF7pKlaOTyj5VdzTpUGFr_tALLTxH5n9bQ"
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
    async with Bot(token=TOKEN) as bot:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())