from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from sqlalchemy import select

from database.crud import get_user, create_user, agree_to_terms
from database.engine import async_session
from database.models import User
from database.settings import is_referral_enabled
from keyboards.common import (
    TEST_NOTICE,
    terms_keyboard,
    pay_keyboard,
    bottom_keyboard,
    banned_keyboard,
    support_keyboard,
)
from keyboards.user.main import main_menu
from utils.notifications import notify_new_user

router = Router()


async def get_main_menu_markup():
    async with async_session() as session:
        referral_enabled = await is_referral_enabled(session)
    return main_menu(referral_enabled=referral_enabled)


async def send_user_home(message: Message) -> None:
    """Отправляет нижнюю навигацию и чистое главное меню."""
    await message.answer(TEST_NOTICE, reply_markup=bottom_keyboard())
    await message.answer(
        "👋 Выбери направление:",
        reply_markup=await get_main_menu_markup(),
    )


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
                "🔒 Для доступа к материалам необходима подписка.\n\n"
                "Стоимость: 500 ₽ (разово, навсегда)\n\n"
                "После оплаты получаешь полный доступ ко всем материалам без ограничений.",
                reply_markup=pay_keyboard()
            )

        else:
            await send_user_home(message)


@router.callback_query(F.data == "terms:accept")
async def accept_terms(callback: CallbackQuery):
    async with async_session() as session:
        await agree_to_terms(session, callback.from_user.id)
        user = await get_user(session, callback.from_user.id)

        if user.has_subscription:
            await callback.message.answer(TEST_NOTICE, reply_markup=bottom_keyboard())
            await callback.message.edit_text(
                "👋 Добро пожаловать! Выбери направление:",
                reply_markup=main_menu(referral_enabled=await is_referral_enabled(session))
            )
        else:
            await callback.message.edit_text(
                "✅ Соглашение принято!\n\n"
                "🔒 Для доступа к материалам необходима подписка.\n\n"
                "Стоимость: 500 ₽ (разово, навсегда)",
                reply_markup=pay_keyboard()
            )
    await callback.answer()


@router.callback_query(F.data == "terms:decline")
async def decline_terms(callback: CallbackQuery):
    await callback.message.edit_text(
        "😔 Без принятия соглашения использование бота невозможно.\n\n"
        "Если передумаешь — нажми /start"
    )
    await callback.answer()


@router.callback_query(F.data == "back:main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "👋 Выбери направление:",
        reply_markup=await get_main_menu_markup()
    )
    await callback.answer()


@router.message(F.text == "🏠 Главное меню")
async def bottom_main_menu(message: Message):
    await message.answer(
        "👋 Выбери направление:",
        reply_markup=await get_main_menu_markup()
    )


@router.message(F.text == "🛠 Тех. поддержка")
async def support(message: Message):
    await message.answer(
        "📬 Контакты\n\n"
        "Выбери, куда обратиться:",
        reply_markup=support_keyboard()
    )
