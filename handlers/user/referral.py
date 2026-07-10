from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, func

from database.engine import async_session
from database.crud import get_user
from database.models import User, ReferralBalance, WithdrawalRequest
from database.settings import get_min_withdrawal, is_referral_enabled, get_referral_reward
from keyboards.user.referral import referral_keyboard, withdraw_cancel_keyboard, after_withdraw_keyboard
from states.user import WithdrawStates
from utils.notifications import notify_withdrawal

router = Router()


async def safe_callback_answer(callback: CallbackQuery, *args, **kwargs) -> None:
    """Отвечает на callback без падения, если Telegram уже закрыл query."""
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest:
        pass


async def get_or_create_balance(session, user_id: int) -> ReferralBalance:
    result = await session.execute(
        select(ReferralBalance).where(ReferralBalance.user_id == user_id)
    )
    balance = result.scalar_one_or_none()

    if not balance:
        balance = ReferralBalance(user_id=user_id)
        session.add(balance)
        await session.commit()
        await session.refresh(balance)

    return balance


@router.callback_query(F.data == "referral")
async def show_referral(callback: CallbackQuery):
    # Важно отвечать сразу, иначе если БД/Telegram get_me тормозят, callback устаревает
    # и появляется ошибка: query is too old and response timeout expired.
    await safe_callback_answer(callback)

    async with async_session() as session:
        user = await get_user(session, callback.from_user.id)
        if not user:
            await callback.message.answer("Пользователь не найден. Нажми /start.")
            return

        referral_on = await is_referral_enabled(session)
        reward = await get_referral_reward(session)
        min_w = await get_min_withdrawal(session)

        result = await session.execute(
            select(func.count()).where(User.referred_by == user.user_id)
        )
        referrals_count = result.scalar() or 0
        balance = await get_or_create_balance(session, user.user_id)

    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.referral_code}"

    if referral_on:
        if balance.balance < min_w:
            withdraw_status = (
                f"⚠️ Минимальная сумма для вывода: {min_w} ₽\n"
                f"Сейчас доступно: {balance.balance} ₽"
            )
        else:
            withdraw_status = f"✅ Доступен вывод: {balance.balance} ₽"

        text = (
            f"💸 Пригласи друга и заработай\n\n"
            f"За каждого приглашённого друга начисляется: {reward} ₽\n"
            f"Минимальная сумма вывода: {min_w} ₽\n\n"
            f"👥 Приглашено друзей: {referrals_count}\n"
            f"💰 Заработано всего: {balance.total_earned} ₽\n"
            f"💳 Доступно к выводу: {balance.balance} ₽\n"
            f"⏳ В обработке: {balance.frozen} ₽\n\n"
            f"{withdraw_status}\n\n"
            f"🔗 Твоя ссылка для приглашения:\n{ref_link}\n\n"
            f"Отправь эту ссылку другу. Когда он зарегистрируется по ней, он будет привязан к тебе как реферал."
        )
    else:
        text = (
            f"💸 Реферальная система\n\n"
            f"Сейчас реферальная программа временно отключена.\n"
            f"Когда она снова будет доступна, здесь появится твоя ссылка и баланс."
        )

    await callback.message.edit_text(
        text,
        reply_markup=referral_keyboard(
            balance.balance,
            min_w,
            referral_on,
            ref_link=ref_link if referral_on else None,
            reward=reward if referral_on else None,
        )
    )


@router.callback_query(F.data == "withdraw:not_enough")
async def withdraw_not_enough(callback: CallbackQuery):
    async with async_session() as session:
        min_w = await get_min_withdrawal(session)
        balance = await get_or_create_balance(session, callback.from_user.id)

    await safe_callback_answer(
        callback,
        f"Минимальная сумма для вывода: {min_w} ₽. Сейчас доступно: {balance.balance} ₽",
        show_alert=True
    )


@router.callback_query(F.data == "withdraw:start")
async def withdraw_start(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        referral_on = await is_referral_enabled(session)
        if not referral_on:
            await safe_callback_answer(
                callback,
                "Реферальная система сейчас отключена.",
                show_alert=True,
            )
            return

        min_w = await get_min_withdrawal(session)
        balance = await get_or_create_balance(session, callback.from_user.id)

        if balance.balance < min_w:
            await safe_callback_answer(
                callback,
                f"Минимальная сумма для вывода: {min_w} ₽. Сейчас доступно: {balance.balance} ₽",
                show_alert=True
            )
            return

        await safe_callback_answer(callback)
        await state.set_state(WithdrawStates.waiting_for_requisites)
        await state.update_data(amount=balance.balance)

        await callback.message.edit_text(
            f"💸 Заявка на вывод\n\n"
            f"Сумма к выводу: {balance.balance} ₽\n\n"
            f"Напиши номер карты или номер телефона для СБП:\n"
            f"например: 79001234567 или 4276 1234 5678 9012",
            reply_markup=withdraw_cancel_keyboard()
        )


@router.message(WithdrawStates.waiting_for_requisites)
async def withdraw_requisites(message: Message, state: FSMContext):
    requisites = message.text.strip()
    data = await state.get_data()
    amount = data.get("amount", 0)

    async with async_session() as session:
        balance = await get_or_create_balance(session, message.from_user.id)
        amount = balance.balance if balance.balance else amount

        if amount <= 0:
            await state.clear()
            await message.answer(
                "⚠️ Сейчас нет средств для вывода.",
                reply_markup=after_withdraw_keyboard()
            )
            return

        balance.frozen = balance.frozen + amount
        balance.balance = max(0, balance.balance - amount)

        request = WithdrawalRequest(
            user_id=message.from_user.id,
            amount=amount
        )
        session.add(request)
        await session.commit()

        await notify_withdrawal(
            bot=message.bot,
            request_id=request.id,
            user_id=message.from_user.id,
            username=message.from_user.username,
            amount=amount,
            requisites=requisites
        )

    await state.clear()
    await message.answer(
        f"✅ Заявка на вывод создана!\n\n"
        f"Сумма: {amount} ₽\n\n"
        f"Мы переведём деньги в течение 24 часов и уведомим тебя.",
        reply_markup=after_withdraw_keyboard()
    )


@router.callback_query(F.data == "withdraw:cancel")
async def withdraw_cancel(callback: CallbackQuery, state: FSMContext):
    await safe_callback_answer(callback)
    await state.clear()
    await callback.message.edit_text(
        "❌ Вывод отменён.",
        reply_markup=after_withdraw_keyboard()
    )
