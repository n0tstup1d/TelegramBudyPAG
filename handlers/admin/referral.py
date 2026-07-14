from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select, func
from sqlalchemy.orm import aliased

from database.engine import async_session
from database.models import User, ReferralBalance
from database.settings import set_setting, is_referral_enabled, get_referral_reward, get_min_withdrawal
from handlers.admin.guards import is_admin
from states.admin import ReferralSettings

router = Router()


async def safe_answer(callback: CallbackQuery, *args, **kwargs) -> None:
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "admin:referral")
async def admin_referral(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        enabled = await is_referral_enabled(session)
        reward = await get_referral_reward(session)
        min_w = await get_min_withdrawal(session)

        total_referrals = await session.scalar(
            select(func.count()).select_from(User).where(User.referred_by.isnot(None))
        )
        total_paid = await session.scalar(
            select(func.sum(ReferralBalance.total_earned)).select_from(ReferralBalance)
        ) or 0
        total_frozen = await session.scalar(
            select(func.sum(ReferralBalance.frozen)).select_from(ReferralBalance)
        ) or 0

        referrer = aliased(User)
        top_result = await session.execute(
            select(referrer.username, referrer.user_id, func.count(User.id).label("count"))
            .join(referrer, User.referred_by == referrer.user_id)
            .group_by(referrer.username, referrer.user_id)
            .order_by(func.count(User.id).desc())
            .limit(3)
        )
        top = top_result.all()

        top_text = ""
        for i, row in enumerate(top, 1):
            name = f"@{row.username}" if row.username else str(row.user_id)
            top_text += f"{i}. {name} — {row.count} чел.\n"

        status = "✅ Включена" if enabled else "❌ Выключена"
        toggle_text = "❌ Выключить" if enabled else "✅ Включить"
        toggle_value = "false" if enabled else "true"

        text = (
            f"👥 Реферальная система\n\n"
            f"Статус: {status}\n"
            f"Награда за реферала: {reward} ₽\n"
            f"Минимум для вывода: {min_w} ₽\n\n"
            f"📊 Статистика:\n"
            f"Всего рефералов: {total_referrals}\n"
            f"Выплачено всего: {total_paid} ₽\n"
            f"Заморожено: {total_frozen} ₽\n\n"
            f"🏆 Топ рефереров:\n{top_text if top_text else 'Пока нет'}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=toggle_text, callback_data=f"admin:referral_toggle:{toggle_value}")],
                [InlineKeyboardButton(text="✏️ Изменить награду", callback_data="admin:referral_reward")],
                [InlineKeyboardButton(text="✏️ Изменить минимум вывода", callback_data="admin:referral_minw")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")],
            ]),
        )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("admin:referral_toggle:"))
async def admin_referral_toggle(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    value = callback.data.split(":")[2]
    async with async_session() as session:
        await set_setting(session, "referral_enabled", value)

    notice = (
        "Реферальная система включена. Проверь платёжное начисление и правила программы."
        if value == "true" else "Реферальная система выключена."
    )
    await safe_answer(callback, notice, show_alert=value == "true")
    await admin_referral(callback)


@router.callback_query(F.data == "admin:referral_reward")
async def admin_change_reward(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(ReferralSettings.waiting_reward)
    await callback.message.edit_text(
        "✏️ Введи новую сумму награды за реферала (в рублях):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:referral")]
        ]),
    )
    await safe_answer(callback)


@router.message(ReferralSettings.waiting_reward)
async def admin_save_reward(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    if not message.text.isdigit():
        await message.answer("⚠️ Введи число")
        return

    async with async_session() as session:
        await set_setting(session, "referral_reward", message.text)

    await state.clear()
    await message.answer(f"✅ Награда изменена на {message.text} ₽")


@router.callback_query(F.data == "admin:referral_minw")
async def admin_change_minw(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(ReferralSettings.waiting_minw)
    await callback.message.edit_text(
        "✏️ Введи новый минимум для вывода (в рублях):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:referral")]
        ]),
    )
    await safe_answer(callback)


@router.message(ReferralSettings.waiting_minw)
async def admin_save_minw(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    if not message.text.isdigit():
        await message.answer("⚠️ Введи число")
        return

    async with async_session() as session:
        await set_setting(session, "min_withdrawal", message.text)

    await state.clear()
    await message.answer(f"✅ Минимум вывода изменён на {message.text} ₽")
