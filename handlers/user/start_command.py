from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message

from datetime import datetime

from misc import BDB, get_text
from keyboards import start_buttons_kb, plan_selection_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user_id = message.from_user.id

    user = BDB.get_user(user_id)

    if user is None:
        BDB.add_user(user_id)
        user = BDB.get_user(user_id)

    user_name = message.from_user.username if message.from_user.username else message.from_user.first_name

    BDB.update_user_field(user_id, "user_name", message.from_user.username)
    BDB.update_user_field(user_id, "first_name", message.from_user.first_name)

    if user["access_granted"] == 0:
        for i in BDB.get_users_by_job_title("admin"):
            await bot.send_message(chat_id=i["telegram_id"],
                                   text=f"<a href='{message.from_user.url}'>@{user_name}</a> Пытается зайти в бота. ID: {message.from_user.id}",
                                   reply_markup=plan_selection_keyboard(user_id))
        await message.answer(text=get_text('NO_ACCESS'))
    elif user["access_granted"] == 1:
        await message.answer(text=f"Твоя підписка активна до: <b>{datetime.strptime(user['subscription_end'], '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y')}</b>", reply_markup=start_buttons_kb)

