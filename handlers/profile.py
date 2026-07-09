from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from utils.notifications import notify_withdrawal
from states.states import WithdrawStates
from database.engine import async_session
from database.models import User, ReferralBalance, WithdrawalRequest
from database.crud import get_user
from database.settings import get_min_withdrawal, is_referral_enabled, get_referral_reward

router = Router()


def profile_keyboard(balance: int, min_withdrawal: int = 200) -> InlineKeyboardMarkup:
    buttons = []
    if balance >= min_withdrawal:
        buttons.append([
            InlineKeyboardButton(text="💸 Вывести средства", callback_data="withdraw:start")
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="withdraw:cancel")]
    ])


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


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    async with async_session() as session:
        user = await get_user(session, callback.from_user.id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
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
        created = user.created_at.strftime("%d.%m.%Y")
        sub_status = "✅ Активна" if user.has_subscription else "❌ Не активна"

        text = (
            f"👤 Твой профиль\n\n"
            f"📅 С нами с: {created}\n"
            f"💳 Подписка: {sub_status}\n"
        )

        if referral_on:
            text += (
                f"\n👥 Реферальная программа:\n"
                f"Награда за друга: {reward} ₽\n"
                f"Приглашено друзей: {referrals_count}\n"
                f"Заработано всего: {balance.total_earned} ₽\n"
                f"Доступно к выводу: {balance.balance} ₽\n\n"
                f"🔗 Твоя ссылка:\n{ref_link}"
            )

        await callback.message.edit_text(
            text,
            reply_markup=profile_keyboard(balance.balance if referral_on else 0, min_w)
        )
    await callback.answer()


@router.callback_query(F.data == "withdraw:start")
async def withdraw_start(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        min_w = await get_min_withdrawal(session)
        balance = await get_or_create_balance(session, callback.from_user.id)

        if balance.balance < min_w:
            await callback.answer(
                f"Минимальная сумма вывода {min_w} ₽",
                show_alert=True
            )
            return

        await state.set_state(WithdrawStates.waiting_for_requisites)
        await state.update_data(amount=balance.balance)

        await callback.message.edit_text(
            f"💸 Вывод средств\n\n"
            f"Сумма к выводу: {balance.balance} ₽\n\n"
            f"Напиши номер карты или номер телефона для СБП:\n"
            f"(например: 79001234567 или 4276 1234 5678 9012)",
            reply_markup=cancel_keyboard()
        )
    await callback.answer()


@router.message(WithdrawStates.waiting_for_requisites)
async def withdraw_requisites(message: Message, state: FSMContext):
    requisites = message.text.strip()
    data = await state.get_data()
    amount = data.get("amount", 0)

    async with async_session() as session:
        balance = await get_or_create_balance(session, message.from_user.id)
        balance.frozen = balance.balance
        balance.balance = 0

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
        reply_markup=profile_keyboard(0)
    )


@router.callback_query(F.data == "withdraw:cancel")
async def withdraw_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Вывод отменён.",
        reply_markup=profile_keyboard(0)
    )
    await callback.answer()