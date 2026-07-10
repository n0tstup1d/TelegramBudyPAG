from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from database.engine import async_session
from database.crud import get_user
from database.settings import is_referral_enabled
from keyboards.user.profile import profile_keyboard

router = Router()


async def build_profile(user_id: int):
    async with async_session() as session:
        user = await get_user(session, user_id)
        if not user:
            return None, None, None

        referral_on = await is_referral_enabled(session)
        created = user.created_at.strftime("%d.%m.%Y")
        sub_status = "✅ Активна" if user.has_subscription else "❌ Не активна"

        text = (
            f"👤 Твой профиль\n\n"
            f"📅 С нами с: {created}\n"
            f"💳 Подписка: {sub_status}"
        )

        if referral_on:
            text += (
                "\n\n💸 Хочешь получить деньги за приглашение друга — "
                "открой реферальную систему ниже."
            )

        return text, profile_keyboard(referral_enabled=referral_on), user


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    text, keyboard, user = await build_profile(callback.from_user.id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(F.text == "👤 Профиль")
async def show_profile_from_bottom(message: Message):
    text, keyboard, user = await build_profile(message.from_user.id)
    if not user:
        await message.answer("Пользователь не найден. Нажми /start.")
        return

    await message.answer(text, reply_markup=keyboard)
