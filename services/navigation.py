from __future__ import annotations

from aiogram.types import Message, CallbackQuery

from database.engine import async_session
from database.crud import get_user
from database.settings import is_referral_enabled, is_shops_enabled
from keyboards.common import RELEASE_NOTICE, bottom_keyboard, support_keyboard, pay_keyboard, SUBSCRIPTION_REQUIRED_TEXT
from keyboards.user.main import main_menu
from services.access import has_access


HOME_TEXT = "👋 Выбери направление:"
SUPPORT_CENTER_TEXT = "📬 Помощь и контакты\n\nВыбери нужный вариант:"


async def get_main_menu_markup():
    """Собирает главное меню с учётом настроек из БД."""
    async with async_session() as session:
        referral_enabled = await is_referral_enabled(session)
        shops_enabled = await is_shops_enabled(session)
    return main_menu(referral_enabled=referral_enabled, shops_enabled=shops_enabled)


async def send_release_notice(message: Message) -> None:
    """Показывает нижнюю навигацию и уведомление о раннем доступе."""
    await message.answer(RELEASE_NOTICE, reply_markup=bottom_keyboard())


async def send_locked_message(message: Message) -> None:
    await message.answer(SUBSCRIPTION_REQUIRED_TEXT, parse_mode="HTML", reply_markup=pay_keyboard())


async def edit_locked_message(callback: CallbackQuery) -> None:
    await callback.message.edit_text(SUBSCRIPTION_REQUIRED_TEXT, parse_mode="HTML", reply_markup=pay_keyboard())


async def send_home(message: Message, *, with_notice: bool = False, text: str = HOME_TEXT) -> None:
    """Отправляет пользователю главный экран только при доступе."""
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)

    if not has_access(user):
        await send_locked_message(message)
        return

    if with_notice:
        await send_release_notice(message)

    await message.answer(text, reply_markup=await get_main_menu_markup())


async def edit_home(callback: CallbackQuery, *, text: str = HOME_TEXT) -> None:
    """Редактирует текущее сообщение в главный экран только при доступе."""
    async with async_session() as session:
        user = await get_user(session, callback.from_user.id)

    if not has_access(user):
        await edit_locked_message(callback)
        return

    await callback.message.edit_text(text, reply_markup=await get_main_menu_markup())


async def send_support_center(message: Message) -> None:
    """Открывает центр помощи и контактов."""
    await message.answer(SUPPORT_CENTER_TEXT, reply_markup=support_keyboard())
