from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from sqlalchemy import select

from database.crud import get_user, create_user, agree_to_terms
from database.engine import async_session
from database.models import User
from keyboards.common import (
    SUBSCRIPTION_REQUIRED_TEXT,
    terms_keyboard,
    pay_keyboard,
    banned_keyboard,
)
from utils.notifications import notify_new_user
from services.navigation import send_home, edit_home, send_support_center

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session() as session:
        referred_by = None
        args = message.text.split()
        if len(args) > 1:
            ref_code = args[1]
            result = await session.execute(
                select(User).where(User.referral_code == ref_code)
            )
            referrer = result.scalar_one_or_none()
            if referrer and referrer.user_id != message.from_user.id:
                referred_by = referrer.user_id

        user = await get_user(session, message.from_user.id)

        if user and user.role == "banned":
            await message.answer(
                "🚫 Ваш аккаунт заблокирован.\n\n"
                "Если считаете это ошибкой — обратитесь в поддержку.",
                reply_markup=banned_keyboard()
            )
            return

        if not user:
            try:
                user = await create_user(
                    session=session,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    full_name=message.from_user.full_name,
                    referred_by=referred_by
                )
                await notify_new_user(
                    bot=message.bot,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    full_name=message.from_user.full_name,
                    referred_by=referred_by
                )
            except Exception:
                user = await get_user(session, message.from_user.id)

            await message.answer(
                "👋 Привет! Я бот по биохакингу.\n\n"
                "Здесь ты найдёшь научно обоснованные материалы о сне, питании, добавках и восстановлении.\n\n"
                "Перед началом прочитай пользовательское соглашение.",
                reply_markup=terms_keyboard()
            )

        elif not user.agreed_to_terms:
            await message.answer(
                "📋 Для продолжения необходимо принять соглашение.",
                reply_markup=terms_keyboard()
            )

        elif not user.has_subscription:
            await message.answer(
                SUBSCRIPTION_REQUIRED_TEXT,
                reply_markup=pay_keyboard()
            )

        else:
            await send_home(message, with_notice=True)


@router.callback_query(F.data == "terms:accept")
async def accept_terms(callback: CallbackQuery):
    async with async_session() as session:
        await agree_to_terms(session, callback.from_user.id)
        user = await get_user(session, callback.from_user.id)

        if user.has_subscription:
            await send_home(callback.message, with_notice=True, text="👋 Добро пожаловать! Выбери направление:")
        else:
            await callback.message.edit_text(
                "✅ Соглашение принято!\n\n" + SUBSCRIPTION_REQUIRED_TEXT,
                reply_markup=pay_keyboard()
            )
    await callback.answer()


@router.callback_query(F.data == "pay")
async def pay_stub(callback: CallbackQuery):
    await callback.answer(
        "Сейчас идёт закрытое тестирование. Доступ выдаётся администратором вручную.",
        show_alert=True,
    )


@router.callback_query(F.data == "terms:decline")
async def decline_terms(callback: CallbackQuery):
    await callback.message.edit_text(
        "😔 Без принятия соглашения использование бота невозможно.\n\n"
        "Если передумаешь — нажми /start"
    )
    await callback.answer()


@router.callback_query(F.data == "back:main")
async def back_to_main(callback: CallbackQuery):
    await edit_home(callback)
    await callback.answer()


@router.message(F.text.in_({"🏠 Главное меню", "🏠 Меню"}))
async def bottom_main_menu(message: Message):
    await send_home(message)


@router.message(F.text.in_({"🛠 Тех. поддержка", "🛠 Поддержка"}))
async def support(message: Message):
    await send_support_center(message)


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
