import json
import sys
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from handlers.user import bot_callback, bot_messages, start_command
from handlers.admin import command

from misc import TOKEN, BDB
from reminder import reminder_payment, kick_expired_once

class PrefixFormatter(logging.Formatter):
    PREFIXES = {
        logging.INFO: "[+]",
        logging.WARNING: "[!]",
        logging.ERROR: "[-]",
        logging.CRITICAL: "[-]",
    }

    def format(self, record):
        record.prefix = self.PREFIXES.get(record.levelno, "[ ]")
        return super().format(record)


def setup_logging():
    log_dir = Path(__file__).resolve().parent / "misc" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "bot.log"
    log_retention_days = 7

    formatter = PrefixFormatter("%(asctime)s %(prefix)s %(name)s: %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=log_retention_days,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(stream_handler)
    root.addHandler(file_handler)
    logging.captureWarnings(True)

    def _handle_exception(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        logging.getLogger(__name__).error("Unhandled exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = _handle_exception

def _asyncio_exception_handler(loop, context):
    err = context.get("exception")
    msg = context.get("message")
    logging.getLogger(__name__).error("Asyncio exception: %s", msg, exc_info=err)

async def _reminder_runner(bot: Bot):
    try:
        await reminder_payment(bot)
    except Exception:
        logging.getLogger(__name__).exception("Reminder task crashed")

async def _startup_kick_runner(bot: Bot):
    try:
        await kick_expired_once(bot)
    except Exception:
        logging.getLogger(__name__).exception("Startup kick sweep crashed")

async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_routers(
        start_command.router,
        command.router,
        bot_callback.router,
        bot_messages.router
    )

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_asyncio_exception_handler)
    asyncio.create_task(_reminder_runner(bot))
    asyncio.create_task(_startup_kick_runner(bot))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    print("[+] BOT STARTING")
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[-] BOT HAS BEEN DISABLE")
        BDB.close()
