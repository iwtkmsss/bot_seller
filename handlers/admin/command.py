import json
import re
from datetime import datetime, timedelta

from aiogram import Router, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, ChatMemberAdministrator, ChatMemberOwner
from aiogram.filters import Command, CommandObject

from filter import UserAdmin
from misc import BDB, get_text

router = Router()

@router.message(Command("admin"), UserAdmin())
async def cmd_admin(message: Message):
    text = (
        "🔒 <b>Админ-панель</b>\n\n"
        "<code>/add_channel &lt;channel_id&gt; [назва]</code> — Добавить канал\n"
        "<code>/remove_channel &lt;channel_id&gt;</code> — Удалить канал\n"
        "/channels — Всі додані канали\n"
        "<code>/add_plan &lt;telegram_id&gt; &lt;назва_плану&gt;</code> - Додати користувачу план\n"
        "<code>/add_tp &lt;telegram_id&gt;</code> - Призначити користувачу посаду tp\n"
        "<code>/remove_tp &lt;telegram_id&gt;</code> - Видалити посаду tp у користувача\n"
        "<code>/add_time &lt;telegram_id&gt; &lt;дата/тривалість&gt;</code>\n\n"
        "📌 Бот для получения ID канала: @username_to_id_bot"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("add_channel"), UserAdmin())
async def cmd_add_channel(message: Message, bot: Bot):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(
            "⚠️ Формат: <code>/add_channel &lt;channel_id&gt; [назва]</code>",
            parse_mode="HTML"
        )
        return

    channel_id = int(parts[1])
    title = parts[2] if len(parts) > 2 else "Без назви"

    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)
        if not isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
            await message.answer("❌ Я не адмін у цьому каналі. Додай мене як адміна і спробуй знову.")
            return
    except TelegramBadRequest:
        await message.answer("❌ Не вдалося отримати інформацію про канал. Перевір ID і додай мене в канал.")
        return

    BDB.add_channel(name=title, channel_id=channel_id)
    await message.answer(f"✅ Канал <code>{channel_id}</code> додано!", parse_mode="HTML")


@router.message(Command("channels"), UserAdmin())
async def cmd_channels(message: Message):
    channels = BDB.get_channels()

    if not channels:
        await message.answer("📭 Список каналів порожній.")
        return

    text = "📋 <b>Список каналів:</b>\n\n"
    for ch in channels:
        text += f"• <code>{ch['id']}</code> — {ch['name']}\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("remove_channel"), UserAdmin())
async def cmd_remove_channel(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "⚠️ Формат: <code>/remove_channel &lt;channel_id&gt;</code>",
            parse_mode="HTML"
        )
        return

    channel_id = int(parts[1])

    BDB.remove_channel_by_id(channel_id)
    await message.answer(f"🗑 Канал <code>{channel_id}</code> видалено.", parse_mode="HTML")


@router.message(Command("add_plan"), UserAdmin())
async def cmd_add_plan(message: Message, bot: Bot):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "⚠️ Формат: <code>/add_plan &lt;telegram_id&gt; &lt;назва_плану&gt;</code>",
            parse_mode="HTML"
        )
        return

    telegram_id = parts[1]
    plan = parts[2]

    channels  = BDB.get_channels()

    if not channels :
        await message.answer("⚠️ У таблиці settings відсутній список доступних планів.")
        return

    channel = next((ch for ch in channels if ch["name"] == plan), None)
    if not channel:
        await message.answer(f"❌ План <b>{plan}</b> не знайдено серед доступних: {', '.join([ch['name'] for ch in channels])}", parse_mode="HTML")
        return

    invite_link = await bot.create_chat_invite_link(chat_id=channel["id"],
                                                    member_limit=1,
                                                    expire_date=datetime.now() + timedelta(days=1))
    BDB.add_subscription_plan(telegram_id, plan)
    user = await bot.get_chat(telegram_id)
    await bot.send_message(chat_id=telegram_id, text=get_text("ADD_NEW_PLAN").format(name=user.first_name,
                                                                                     link=invite_link.invite_link))
    await message.answer(f"✅ Користувачу <code>{telegram_id}</code> додано план <b>{plan}</b>.", parse_mode="HTML")


@router.message(Command("add_tp"), UserAdmin())
async def add_tp_cmd(message: Message):
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Формат: <code>/add_tp &lt;telegram_id&gt;</code>", parse_mode="HTML")
        return

    telegram_id = parts[1]

    user = BDB.get_user(telegram_id)
    if not user:
        await message.answer("❌ Користувача не знайдено.")
        return

    BDB.update_user_field(telegram_id, "job_title", "tp")
    await message.answer(f"✅ Користувачу {telegram_id} призначено посаду <b>tp</b>.", parse_mode="HTML")


@router.message(Command("remove_tp"), UserAdmin())
async def remove_tp_cmd(message: Message):
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Формат: <code>/remove_tp &lt;telegram_id&gt;</code>", parse_mode="HTML")
        return

    telegram_id = parts[1]

    user = BDB.get_user(telegram_id)
    if not user:
        await message.answer("❌ Користувача не знайдено.")
        return

    BDB.update_user_field(telegram_id, "job_title", "user")
    await message.answer(f"🗑 Посаду користувача {telegram_id} видалено.", parse_mode="HTML")


def _parse_until(arg: str) -> datetime | None:
    arg = arg.strip()

    # 1) Відносні формати: +7d / +12h / +3w / +6m (m ~ 30 днів)
    m = re.fullmatch(r"\+(\d+)\s*([dhwm])", arg, flags=re.I)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        now = datetime.now()
        if unit == "d":
            return now + timedelta(days=n)
        if unit == "h":
            return now + timedelta(hours=n)
        if unit == "w":
            return now + timedelta(weeks=n)
        if unit == "m":
            return now + timedelta(days=30 * n)

    # 2) Абсолютна дата + час: YYYY-MM-DD HH:MM
    for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(arg, fmt)
        except ValueError:
            pass

    # 3) Лише дата (ставимо 23:59 локально)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            d = datetime.strptime(arg, fmt)
            return d.replace(hour=23, minute=59)
        except ValueError:
            pass

    return None

# ---- команда: /add_time <telegram_id> <until> ----
@router.message(Command("add_time"), UserAdmin())
async def cmd_add_time(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "⚠️ Формат:\n"
            "<code>/add_time &lt;telegram_id&gt; &lt;дата/тривалість&gt;</code>\n\n"
            "Приклади:\n"
            "• <code>/add_time 123456789 2025-09-07</code>\n"
            "• <code>/add_time 123456789 07.09.2025 18:00</code>\n"
            "• <code>/add_time 123456789 +7d</code>\n"
            "• <code>/add_time 123456789 +12h</code>",
            parse_mode="HTML",
        )
        return

    telegram_id = parts[1]
    until_raw = parts[2]

    # Перевіримо, що користувач існує
    user = BDB.get_user(telegram_id)
    if not user:
        await message.answer("❌ Користувача не знайдено.")
        return

    until_dt = _parse_until(until_raw)
    if not until_dt:
        await message.answer("❌ Неможливо розпізнати дату/тривалість. Перевір формат.")
        return

    now = datetime.now()
    if until_dt <= now:
        await message.answer("❌ Дата закінчення повинна бути в майбутньому.")
        return

    # Зберігаємо в ISO (без таймзони). Якщо потрібно — можна додати tzinfo/UTC.
    until_dt = until_dt.replace(microsecond=0)
    BDB.update_user_field(
        telegram_id,
        "subscription_end",
        until_dt.strftime("%Y-%m-%d %H:%M:%S.%f")
    )

    # Лог зміни часу від адміна
    try:
        admin_name = message.from_user.username or message.from_user.first_name
        BDB.create_payment_entry(
            telegram_id=int(telegram_id),
            method="admin_add_time",
            amount=0,
            plan=None,
            status="applied",
            user_name=user.get("user_name"),
            first_name=user.get("first_name"),
            admin_id=message.from_user.id,
            admin_name=admin_name,
            old_subscription_end=old_subscription_end,
            new_subscription_end=until_dt.strftime("%Y-%m-%d %H:%M:%S.%f"),
            payload=message.text,
            description="admin add_time",
            raw_response=None,
        )
    except Exception:
        pass

    # Опціонально: повідомити користувача (забери/залиш за бажанням)
    # await bot.send_message(chat_id=telegram_id, text=f"Ваш доступ подовжено до {until_dt:%d.%m.%Y %H:%M}")

    await message.answer(
        f"✅ Користувачу <code>{telegram_id}</code> встановлено термін до <b>{until_dt:%d.%m.%Y %H:%M}</b>.",
        parse_mode="HTML",
    )
