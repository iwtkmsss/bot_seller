import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from keyboards import payment_kb
from misc import BDB, get_text

TOKEN = "YOUR_TOKEN_HERE"
KYIV = ZoneInfo("Europe/Kyiv")        # <<— ключова таймзона

STAGES = [
    (5.0, "IN_5_DAYS", "5"),
    (3.0, "IN_3_DAYS", "3"),
    (2.0, "IN_2_DAYS", "2"),
    (1.0, "IN_1_DAYS", "1"),
    (0.5, "IN_12_HOURS", "0.5"),
    (0.0, "KICK", "expired"),
]

CHECK_INTERVAL_SECONDS = 60

def _parse_dt_kyiv(s: str) -> datetime | None:
    """
    Парсимо datetime зі строк БД як локальний КИЇВСЬКИЙ час (aware, Europe/Kyiv).
    Якщо у тебе в БД час уже в Києві — просто ставимо tzinfo=KYIV.
    Якщо в БД іноді без мікросекунд – ловимо обидва формати.
    """
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            naive = datetime.strptime(s, fmt)
            return naive.replace(tzinfo=KYIV)   # інтерпретуємо як локальний київський
        except ValueError:
            continue
    return None

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
    BDB.update_user_field(tg_id, "notified_marks", json.dumps(sorted(list(marks), key=lambda x: (x=="expired", x))))

async def _send_stage_message(bot: Bot, user: dict, stage_key: str, mark: str):
    tg_id = user["telegram_id"]
    try:
        user_name = user.get("first_name") or (await bot.get_chat(tg_id)).first_name
    except Exception:
        user_name = "Друже"

    if mark == "expired":
        text = get_text(stage_key)
        channels = BDB.get_channels()
        for ch in channels:
            channel_id = ch["id"]
            try:
                await bot.ban_chat_member(chat_id=channel_id, user_id=tg_id)
                await bot.unban_chat_member(chat_id=channel_id, user_id=tg_id)
            except Exception as e:
                print(f"❌ Не вдалося вигнати {tg_id} з {channel_id}: {e}")
        try:
            await bot.send_message(chat_id=tg_id, text=text)
        except Exception as e:
            print(f"❌ Не вдалося надіслати повідомлення {tg_id}: {e}")
        return

    try:
        text = get_text(stage_key).format(name=user_name)
    except Exception:
        text = "Нагадування: завершується доступ."
    try:
        await bot.send_message(chat_id=tg_id, text=text, reply_markup=payment_kb)
    except Exception as e:
        print(f"❌ Не вдалося надіслати попередження {tg_id} ({mark}): {e}")

async def send_warning_once(bot: Bot, user: dict, days_left: float):
    marks = _load_marks(user)
    for stage_days, stage_key, mark in STAGES:
        if days_left <= stage_days and (mark not in marks):
            await _send_stage_message(bot, user, stage_key, mark)
            marks.add(mark)
            _save_marks(user["telegram_id"], marks)
            break

async def reminder_payment(bot: Bot):
    while True:
        now = datetime.now(KYIV)  # <<— поточний час саме Києва

        for user in BDB.get_users_by_job_title("user"):
            sub_end_raw = user.get("subscription_end")
            sub_end = _parse_dt_kyiv(sub_end_raw)
            if not sub_end:
                continue

            # різниця у таймзоні Києва (DST враховується автоматично)
            seconds_left = (sub_end - now).total_seconds()
            days_left = seconds_left / 86400.0

            try:
                await send_warning_once(bot, user, days_left)
            except Exception as e:
                print(f"❌ Помилка при обробці користувача {user.get('telegram_id')}: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

