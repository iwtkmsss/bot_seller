from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message

import json

from misc import BDB, get_text, parse_subscription_end
from keyboards import start_buttons_kb, plan_selection_keyboard

router = Router()


def _load_marks(user: dict) -> set[str]:
    raw = user.get("notified_marks") or "[]"
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            return {str(x) for x in arr}
    except Exception:
        pass
    return set()

def _save_marks(tg_id: int | str, marks: set[str]):
    from misc import BDB
    BDB.update_user_field(tg_id, "notified_marks", json.dumps(sorted(list(marks))))




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
        marks = _load_marks(user)
        if "admin_notified" not in marks:
            for i in BDB.get_users_by_job_title("admin"):
                await bot.send_message(chat_id=i["telegram_id"],
                                       text=f"<a href='{message.from_user.url}'>@{user_name}</a> пытается зайти в бота. ID: {message.from_user.id}",
                                       reply_markup=plan_selection_keyboard(user_id))
            marks.add("admin_notified")
            _save_marks(user_id, marks)
        await message.answer(text=get_text('NO_ACCESS'))
    elif user["access_granted"] == 1:
        sub_end = parse_subscription_end(user.get("subscription_end"))
        end_text = sub_end.strftime("%d.%m.%Y") if sub_end else (user.get("subscription_end") or "unknown")
        await message.answer(text=f"Твоя підписка активна до: <b>{end_text}</b>", reply_markup=start_buttons_kb)

