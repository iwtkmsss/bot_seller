import json
import sys
import logging
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from handlers.user import bot_callback, bot_messages, start_command
from handlers.admin import command

from misc import TOKEN, BDB
from reminder import reminder_payment

async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_routers(
        start_command.router,
        command.router,
        bot_callback.router,
        bot_messages.router
    )

    asyncio.create_task(reminder_payment(bot))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    print("[+] BOT STARTING")
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[-] BOT HAS BEEN DISABLE")
        BDB.close()
