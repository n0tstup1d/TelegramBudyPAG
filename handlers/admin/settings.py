from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from database.engine import async_session
from database.settings import is_referral_enabled, is_shops_enabled, set_setting
from handlers.admin.guards import is_admin
from keyboards.admin.settings import admin_settings_menu

router = Router()


async def safe_answer(callback: CallbackQuery, *args, **kwargs) -> None:
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "admin:settings")
async def admin_settings(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        shops_enabled = await is_shops_enabled(session)
        referral_enabled = await is_referral_enabled(session)

    shops_status = "✅ Показывается" if shops_enabled else "❌ Скрыта"
    referral_status = "✅ Включена" if referral_enabled else "❌ Выключена"

    await callback.message.edit_text(
        "⚙️ Настройки проекта\n\n"
        f"🏪 Кнопка магазинов: {shops_status}\n"
        f"👥 Реферальная система: {referral_status}\n\n"
        "По умолчанию обе функции выключены. Включай реферальную систему только после подключения "
        "начислений по подтверждённой оплате и правил программы; магазины — после оформления рекламы/партнёрства.\n\n"
        "Выбери, что изменить:",
        reply_markup=admin_settings_menu(
            shops_enabled=shops_enabled,
            referral_enabled=referral_enabled,
        ),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("admin:settings:shops:"))
async def admin_toggle_shops(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    value = callback.data.split(":")[-1]
    async with async_session() as session:
        await set_setting(session, "shops_enabled", value)

    notice = (
        "Раздел магазинов включён. Проверь маркировку рекламы и договоры."
        if value == "true" else "Раздел магазинов скрыт."
    )
    await safe_answer(callback, notice, show_alert=value == "true")
    await admin_settings(callback)


@router.callback_query(F.data.startswith("admin:settings:referral:"))
async def admin_toggle_referral(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    value = callback.data.split(":")[-1]
    async with async_session() as session:
        await set_setting(session, "referral_enabled", value)

    notice = (
        "Реферальная система включена. Не запускай её до подключения начисления только после подтверждённой оплаты."
        if value == "true" else "Реферальная система выключена."
    )
    await safe_answer(callback, notice, show_alert=value == "true")
    await admin_settings(callback)
