from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from handlers.admin.guards import is_admin
from keyboards.admin.main import admin_menu
from keyboards.admin.users import users_menu

router = Router()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return

    await message.answer("🔧 Панель администратора", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:menu")
async def admin_back(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    await callback.message.edit_text("🔧 Панель администратора", reply_markup=admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:roles")
async def admin_roles(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "⚙️ Назначение ролей\n\nВыбери пользователя или найди его по Telegram ID / username.",
        reply_markup=users_menu(),
    )
    await callback.answer()
