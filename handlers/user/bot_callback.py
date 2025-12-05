from asyncio import sleep

from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from misc import create_invoice, check_invoice, BDB, get_text, get_channel_id_from_list, check_payment_received, CRYPTO_ADDRESS, parse_subscription_end, normalize_subscription_end
from keyboards import payment_cb_kb, options_payment_kb, method_payment_kb, start_buttons_kb, cancel_kb, \
    confirm_cancel_kb, plan_selection_keyboard

router = Router()

plans = {
    "one_month": 1,
    "three_months": 3,
    "six_months": 6
}
date_ = {
    "one_month": 1,
    "two_month": 2,
    "three_month": 3,
    "until": datetime(2025, 9, 8, 00, 00, 00, 111111)
}

@router.callback_query(F.data.startswith("toggle_plan:"))
async def toggle_plan_callback(callback: CallbackQuery, state: FSMContext):
    _, tg_id, plan_name = callback.data.split(":", 2)

    data = await state.get_data()
    selected = data.get("selected_plans", [])

    if plan_name in selected:
        selected.remove(plan_name)
    else:
        selected.append(plan_name)

    await state.update_data(selected_plans=selected)

    await callback.message.edit_reply_markup(
        reply_markup=plan_selection_keyboard(int(tg_id), selected, data.get("selected_date"))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_date:"))
async def toggle_date_callback(callback: CallbackQuery, state: FSMContext):
    _, tg_id, date = callback.data.split(":", 2)

    data = await state.get_data()
    selected = data.get("selected_plans", [])

    if date == data.get("selected_date"):
        return

    await state.update_data(selected_date=date)

    await callback.message.edit_reply_markup(
        reply_markup=plan_selection_keyboard(int(tg_id), selected, date)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_plans:"))
async def confirm_plans_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    _, user_id = callback.data.split(":", 1)
    data = await state.get_data()
    selected = data.get("selected_plans", [])
    selected_date = data.get("selected_date", "one_month")

    print(selected, selected_date)

    months = date_.get(selected_date, 1)
    new_end = datetime.now() + relativedelta(months=months)


    BDB.update_user_field(user_id, "subscription_end", normalize_subscription_end(new_end))

    plans_text = "\n".join(selected)
    await callback.message.answer(f"✅ Вибрано плани: \n{plans_text}")

    # Логіка для підтвердження планів

    BDB.update_user_field(user_id, "access_granted", 1)

    
    expire_time = datetime.now() + timedelta(days=1)

    invite_links = []
    for index, plan in enumerate(selected):
        plan_id = get_channel_id_from_list(plan)

        invite_link = await bot.create_chat_invite_link(chat_id=plan_id, member_limit=1, expire_date=expire_time)
        invite_links.append(f"{index+1} посилання - <a href='{invite_link.invite_link}'>{plan}</a>")
        BDB.add_subscription_plan(user_id, plan)

    await bot.send_message(text=get_text("ACCESS_IS_AVAILABLE").format(links="\n".join(invite_links)),
                           chat_id=user_id,
                           reply_markup=start_buttons_kb)
    
    await state.clear()
    await callback.answer("Плани підтверджено.")


@router.callback_query(F.data == "check_subscription")
async def check_subscription_call(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user = BDB.get_user(user_id)

    sub_end = parse_subscription_end(user.get("subscription_end"))
    end_text = sub_end.strftime("%d.%m.%Y") if sub_end else (user.get("subscription_end") or "unknown")
    await callback_query.message.answer(
        text=f"Твоя підписка активна до: <b>{end_text}</b>",
        reply_markup=start_buttons_kb)



@router.callback_query(F.data == "payment_cryptobot")
async def my_orders_call(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    plan = data.get("plan")

    await state.update_data(method_payment="payment_cryptobot")

    user_id = callback_query.from_user.id
    user = BDB.get_user(user_id)
    user_name = user.get("user_name") or callback_query.from_user.username
    first_name = user.get("first_name") or callback_query.from_user.first_name
    BDB.update_user_field(user_id, "payment", 1)

    invoice = create_invoice(
        amount=int(amount),
        payload=str(user['id'])
    )

    payment_id = BDB.create_payment_entry(
        telegram_id=user_id,
        method="cryptobot",
        amount=int(amount),
        plan=plan,
        status="pending",
        provider_invoice_id=str(invoice.get("invoice_id")),
        pay_url=invoice.get("pay_url"),
        payload=str(user['id']),
        description=invoice.get("description"),
        raw_response=invoice,
        user_name=user_name,
        first_name=first_name,
    )

    await state.update_data(markup=(payment_cb_kb(invoice["pay_url"], invoice["invoice_id"]).model_dump()),
                            payment_id=payment_id)
    await callback_query.message.edit_text(text=get_text("PAYMENT_CRYPTO_BOT"),
                                        reply_markup=payment_cb_kb(invoice["pay_url"], invoice["invoice_id"]),
    )
    payment_finished = False
    try:
        for _ in range(180):
            invoice_data = check_invoice(int(invoice["invoice_id"]))
            status = invoice_data.get("status")

            if payment_id:
                BDB.update_payment_entry(
                    payment_id,
                    status=status,
                    paid_at=invoice_data.get("paid_at"),
                    raw_response=invoice_data,
                )

            user = BDB.get_user(user_id)
            if user and user.get("payment") == 0:
                if payment_id:
                    BDB.update_payment_entry(payment_id, status="canceled")
                payment_finished = True
                return

            if status == "paid":
                user = BDB.get_user(user_id)

                current_end = parse_subscription_end(user.get("subscription_end")) or datetime.now()
                subscription_end = current_end + relativedelta(months=plans[plan])

                BDB.update_user_field(
                    user_id,
                    "subscription_end",
                    normalize_subscription_end(subscription_end)
                )
                await callback_query.message.answer(
                    text=get_text("SUBSCRIPTION_EXTENDED").format(date=subscription_end.strftime("%d.%m.%Y")))
                BDB.update_user_field(user_id, "payment", 0)
                BDB.update_user_field(user_id, "notified_marks", "[]")
                try:
                    await callback_query.message.delete()
                except Exception as e:
                    pass
                if payment_id:
                    BDB.update_payment_entry(
                        payment_id,
                        status="paid",
                        paid_at=invoice_data.get("paid_at"),
                        raw_response=invoice_data,
                    )
                payment_finished = True
                return
            await sleep(10)
        await callback_query.message.answer(text="Упсс... Оплату не побачив 😥")
        await callback_query.message.delete()
        if payment_id:
            BDB.update_payment_entry(payment_id, status="timeout")
        payment_finished = True
    finally:
        BDB.update_user_field(user_id, "payment", 0)
        if payment_id and not payment_finished:
            BDB.update_payment_entry(payment_id, status="canceled")
    
    
@router.callback_query(F.data == "payment_usdt")
async def payment_usdt_call(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount") 
    plan = data.get("plan")
    user_id = callback_query.from_user.id
    
    user = BDB.get_user(user_id)
    if user.get("payment") == 1:
        await callback_query.message.answer("Оплата вже обробляється. Дочекайтесь, будь ласка.")
        return

    await state.update_data(method_payment="payment_usdt")

    address = BDB.get_free_crypto_address()
    BDB.mark_address_as_used(address)

    if not address: 
        await callback_query.message.answer("❌ Всі адреси зайняті. Спробуй пізніше.")
        return
    
    BDB.update_user_field(user_id, "payment", 1)

    start_time = datetime.now()
    user_name = user.get("user_name") or callback_query.from_user.username
    first_name = user.get("first_name") or callback_query.from_user.first_name
    payment_id = BDB.create_payment_entry(
        telegram_id=user_id,
        method="usdt_trc20",
        amount=int(amount),
        plan=plan,
        status="pending",
        wallet_address=address,
        raw_response={"start_time": start_time.isoformat()},
        user_name=user_name,
        first_name=first_name,
    )
    await state.update_data(payment_id=payment_id)

    await callback_query.message.edit_text(
        text=get_text("PAYMENT_CRYPTO").format(address=address, amount=amount),
    reply_markup=cancel_kb)
    
    payment_finished = False
    try:
        for _ in range(90):
            user = BDB.get_user(user_id)
            result_payment =  await check_payment_received(address, amount, start_time)
            
            if user["payment"] == 0:
                if payment_id:
                    BDB.update_payment_entry(payment_id, status="canceled")
                payment_finished = True
                return
            
            if result_payment:
                current_end = parse_subscription_end(user.get("subscription_end")) or datetime.now()
                subscription_end = current_end + relativedelta(months=plans[plan])
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
                if payment_id:
                    BDB.update_payment_entry(
                        payment_id,
                        status="paid",
                        tx_hash=result_payment.get("tx_id"),
                        tx_from=result_payment.get("from"),
                        tx_to=result_payment.get("to"),
                        tx_value=result_payment.get("value"),
                        tx_timestamp=result_payment.get("block_timestamp").isoformat() if result_payment.get("block_timestamp") else None,
                        paid_at=result_payment.get("block_timestamp").isoformat() if result_payment.get("block_timestamp") else None,
                        raw_response=result_payment,
                    )
                
                payment_finished = True
                return
            
            await sleep(10)
        await callback_query.message.answer(text="Упсс... Оплату не побачив 😥")
        await callback_query.message.delete()
        if payment_id:
            BDB.update_payment_entry(payment_id, status="timeout")
        payment_finished = True
    finally:
        BDB.update_user_field(user_id, "payment", 0)
        if address != CRYPTO_ADDRESS:
            BDB.unmark_address_as_used(address)
        if payment_id and not payment_finished:
            BDB.update_payment_entry(payment_id, status="canceled")


@router.callback_query(F.data == "payment")
async def payment_call(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    payment = BDB.get_user(user_id)["payment"]
    if payment == 1:
        await callback_query.message.answer(text="Спочатку закінчи з старою оплатою 😊")
        return
    await callback_query.message.answer(text=get_text("SUBSCRIPTION_OPTIONS"), reply_markup=options_payment_kb)


@router.callback_query(F.data == "cancel")
async def cancel_call(callback_query: CallbackQuery):
    await callback_query.message.edit_reply_markup(reply_markup=confirm_cancel_kb)


@router.callback_query(F.data == "cancel_confirm")
async def cancel_confirm_call(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get("payment_id")
    if payment_id:
        BDB.update_payment_entry(payment_id, status="canceled")
    BDB.update_user_field(callback_query.from_user.id, "payment", 0)
    await callback_query.message.answer(text="🥲 Оплату відхилено")
    await callback_query.message.delete()


@router.callback_query(F.data == "back_cancel")
async def back_cancel_call(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    method_payment = data.get("method_payment")

    if method_payment == "payment_usdt":
        markup = cancel_kb
    else:
        markup_dict = data.get("markup")
        markup = InlineKeyboardMarkup(**markup_dict)

    await callback_query.message.edit_reply_markup(
        reply_markup=markup)


@router.callback_query(F.data.startswith("options_payment_"))
async def options_payment_call(callback_query: CallbackQuery, state: FSMContext):
    option_payment = callback_query.data.split("options_payment_")[1]

    if option_payment == "one_month":
        amount = 50
    elif option_payment == "three_months":
        amount = 135
    elif option_payment == "six_months":
        amount = 250
    else:
        await callback_query.answer("Невідома опція", show_alert=True)
        return
    
    await state.update_data(amount=amount)
    await state.update_data(plan=option_payment)

    await callback_query.message.edit_text(text=get_text("PAYMENT"), reply_markup=method_payment_kb)


@router.callback_query(F.data == "back_to_payment_options")
async def back_to_payment_options(callback_query: CallbackQuery):
    await callback_query.message.edit_text(text=get_text("SUBSCRIPTION_OPTIONS"), reply_markup=options_payment_kb)
    await callback_query.answer()
