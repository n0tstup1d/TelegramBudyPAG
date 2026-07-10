from __future__ import annotations

from aiogram.types import Message, CallbackQuery

from database.engine import async_session
from database.settings import is_referral_enabled
from keyboards.common import TEST_NOTICE, bottom_keyboard, support_keyboard
from keyboards.user.main import main_menu


HOME_TEXT = "👋 Выбери направление:"
SUPPORT_CENTER_TEXT = "📬 Помощь и контакты\n\nВыбери нужный вариант:"


async def get_main_menu_markup():
    """Собирает главное меню с учётом настроек из БД."""
    async with async_session() as session:
        referral_enabled = await is_referral_enabled(session)
    return main_menu(referral_enabled=referral_enabled)


async def send_test_notice(message: Message) -> None:
    """Показывает нижнюю навигацию и тестовый дисклеймер."""
    await message.answer(TEST_NOTICE, reply_markup=bottom_keyboard())


async def send_home(message: Message, *, with_notice: bool = False, text: str = HOME_TEXT) -> None:
    """Отправляет пользователю главный экран."""
    if with_notice:
        await send_test_notice(message)
    await message.answer(text, reply_markup=await get_main_menu_markup())


async def edit_home(callback: CallbackQuery, *, text: str = HOME_TEXT) -> None:
    """Редактирует текущее сообщение в главный экран."""
    await callback.message.edit_text(text, reply_markup=await get_main_menu_markup())


async def send_support_center(message: Message) -> None:
    """Открывает центр помощи и контактов."""
    await message.answer(SUPPORT_CENTER_TEXT, reply_markup=support_keyboard())
