import asyncio
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot

from keyboards import payment_kb
from misc import BDB, get_text, normalize_subscription_end

TOKEN = "YOUR_TOKEN_HERE"
KYIV = ZoneInfo("Europe/Kyiv")        # <<— ключова таймзона

logger = logging.getLogger(__name__)

STAGES = [
    (5.0, "IN_5_DAYS", "5"),
    (3.0, "IN_3_DAYS", "3"),
    (2.0, "IN_2_DAYS", "2"),
    (1.0, "IN_1_DAYS", "1"),
    (0.5, "IN_12_HOURS", "0.5"),
    (0.0, "KICK", "expired"),
]

CHECK_INTERVAL_SECONDS = 60

def _parse_dt_kyiv(s: str | datetime) -> datetime | None:
    """
    Парсимо datetime зі строк БД як локальний КИЇВСЬКИЙ час (aware, Europe/Kyiv).
    Підтримуємо:
      - ISO з "T" / "Z"
      - без мікросекунд
      - без секунд
      - лише дату (ставимо 23:59)
    """
    if not s:
        return None
    if isinstance(s, datetime):
        if s.tzinfo:
            return s.astimezone(KYIV)
        return s.replace(tzinfo=KYIV)

    value = str(s).strip()
    if not value:
        return None

    value = value.replace("T", " ")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo:
            return dt.astimezone(KYIV)
        if (" " not in value) and (":" not in value):
            dt = dt.replace(hour=23, minute=59)
        return dt.replace(tzinfo=KYIV)
    except ValueError:
        pass

    date_only = {"%Y-%m-%d", "%d.%m.%Y"}
    formats = (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if fmt in date_only:
                dt = dt.replace(hour=23, minute=59)
            return dt.replace(tzinfo=KYIV)
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

def _rollback_subscription(user: dict, *, days: int = 5, reason: str = "") -> None:
    tg_id = user.get("telegram_id")
    now = datetime.now(KYIV)
    current_end = _parse_dt_kyiv(user.get("subscription_end"))
    if current_end and current_end > now:
        logger.info(
            "Skip rollback: user=%s current_end=%s reason=%s",
            tg_id,
            current_end.isoformat(),
            reason or "kick_failed",
        )
        return

    new_end = now + timedelta(days=days)
    normalized = normalize_subscription_end(new_end)
    BDB.update_user_field(tg_id, "subscription_end", normalized)
    BDB.update_user_field(tg_id, "notified_marks", "[]")
    logger.warning(
        "Rollback subscription: user=%s new_end=%s reason=%s",
        tg_id,
        normalized,
        reason or "kick_failed",
    )

async def _send_stage_message(bot: Bot, user: dict, stage_key: str, mark: str) -> bool:
    tg_id = user["telegram_id"]
    try:
        user_name = user.get("first_name") or (await bot.get_chat(tg_id)).first_name
    except Exception:
        user_name = "Друже"

    if mark == "expired":
        text = get_text(stage_key)
        channels = BDB.get_channels()
        kick_ok = True
        if not channels:
            logger.warning("No channels configured to kick user %s", tg_id)
        for ch in channels:
            channel_id = ch["id"]
            try:
                await bot.ban_chat_member(chat_id=channel_id, user_id=tg_id)
                await bot.unban_chat_member(chat_id=channel_id, user_id=tg_id)
                logger.info("Kick success: user=%s channel=%s", tg_id, channel_id)
            except Exception as e:
                kick_ok = False
                logger.error("Kick failed: user=%s channel=%s error=%s", tg_id, channel_id, e)
        try:
            await bot.send_message(chat_id=tg_id, text=text)
            logger.info("Kick message sent: user=%s", tg_id)
        except Exception as e:
            logger.error("Kick message failed: user=%s error=%s", tg_id, e)
        return kick_ok

    try:
        text = get_text(stage_key).format(name=user_name)
    except Exception:
        text = "Нагадування: завершується доступ."
    try:
        await bot.send_message(chat_id=tg_id, text=text, reply_markup=payment_kb)
        logger.info("Warning sent: user=%s mark=%s", tg_id, mark)
    except Exception as e:
        logger.error("Warning send failed: user=%s mark=%s error=%s", tg_id, mark, e)
    return True

async def send_warning_once(bot: Bot, user: dict, days_left: float):
    marks = _load_marks(user)
    for stage_days, stage_key, mark in STAGES:
        if days_left <= stage_days and (mark not in marks):
            should_mark = await _send_stage_message(bot, user, stage_key, mark)
            if should_mark:
                marks.add(mark)
                _save_marks(user["telegram_id"], marks)
            else:
                logger.warning("Skip marking expired for user=%s due to kick failure", user["telegram_id"])
                if mark == "expired":
                    _rollback_subscription(user, days=5, reason="kick_failed")
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
            except Exception:
                logger.exception(
                    "Error processing user: %s",
                    user.get("telegram_id"),
                )

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def kick_expired_once(bot: Bot):
    """
    One-time sweep on startup: try to kick users whose subscription already expired
    (even if they were already marked as expired).
    """
    now = datetime.now(KYIV)
    candidates = 0
    kicked = 0
    marked_before = 0
    no_date = 0
    errors = 0

    for user in BDB.get_users_by_job_title("user"):
        sub_end_raw = user.get("subscription_end")
        sub_end = _parse_dt_kyiv(sub_end_raw)
        if not sub_end:
            no_date += 1
            continue
        if sub_end > now:
            continue

        marks = _load_marks(user)
        had_expired_mark = "expired" in marks
        if had_expired_mark:
            marked_before += 1

        candidates += 1
        try:
            ok = await _send_stage_message(bot, user, "KICK", "expired")
            if ok:
                kicked += 1
            else:
                _rollback_subscription(user, days=5, reason="startup_kick_failed")
        except Exception:
            errors += 1
            logger.exception("Startup kick failed: user=%s", user.get("telegram_id"))
            _rollback_subscription(user, days=5, reason="startup_kick_exception")

    logger.info(
        "Startup kick sweep done: candidates=%s kicked=%s marked_before=%s no_date=%s errors=%s",
        candidates,
        kicked,
        marked_before,
        no_date,
        errors,
    )

