from aiogram.utils.keyboard import InlineKeyboardButton, InlineKeyboardMarkup, InlineKeyboardBuilder

from misc import BDB


start_buttons_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Зв'язок з адміном", url="https://t.me/refundery")
        ],
        [
            InlineKeyboardButton(text="Продовжити підписку", callback_data="payment")
        ],
        [
            InlineKeyboardButton(text="Перевірити підписку", callback_data="check_subscription")
        ]
    ]
)

def plan_selection_keyboard(tg_id: int, selected: list[str] = [], selected_date = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for plan in BDB.get_channels():
        name = plan["name"]
        checked = "✅" if name in selected else "❌"
        kb.button(text=f"{checked} {name}", callback_data=f"toggle_plan:{tg_id}:{name}")

    kb.row(InlineKeyboardButton(text="1️⃣ Місяць" + ("✅" if "one_month" == selected_date else "❌"),
                                callback_data=f"toggle_date:{tg_id}:one_month"))
    kb.row(InlineKeyboardButton(text="2️⃣ Місяці" + ("✅" if "two_month" == selected_date else "❌"),
                                callback_data=f"toggle_date:{tg_id}:two_month"))
    kb.row(InlineKeyboardButton(text="3️⃣ місяці" + ("✅" if "three_month" == selected_date else "❌"),
                                callback_data=f"toggle_date:{tg_id}:three_month"))

    kb.button(text="✅ Підтвердити", callback_data=f"confirm_plans:{tg_id}")
    kb.adjust(1)

    return kb.as_markup()
    

def payment_cb_kb(pay_url, invoice_id):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💸 Оплатити", url=pay_url)
            ],
            [
                InlineKeyboardButton(text="❌ Відмінити операцію", callback_data="cancel")
            ]
        ]
    )
    return kb


payment_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Оплатити 💰", callback_data="payment")
        ]
    ]
)

method_payment_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Оплата USDT", callback_data="payment_usdt")
        ],
        [
                InlineKeyboardButton(text="Оплата CryptoBot", callback_data="payment_cryptobot")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back_to_payment_options")
        ]
    ]
)

options_payment_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣ Місяць", callback_data="options_payment_one_month"),
        ],
        [
            InlineKeyboardButton(text="3️⃣ Місяці", callback_data="options_payment_three_months"),
        ],
        [
            InlineKeyboardButton(text="6️⃣ Місяців", callback_data="options_payment_six_months"),
        ]
    ]
)

cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Відмінити операцію", callback_data="cancel")
        ]
    ]
)

confirm_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Підтвердити відміну", callback_data="cancel_confirm")
        ],
        [
            InlineKeyboardButton(text="◀️ Назад", callback_data="back_cancel")
        ]
    ]
)
