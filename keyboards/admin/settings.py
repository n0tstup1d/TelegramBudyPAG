from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_settings_menu(*, shops_enabled: bool, referral_enabled: bool) -> InlineKeyboardMarkup:
    shops_text = "❌ Скрыть кнопку магазинов" if shops_enabled else "✅ Показать кнопку магазинов"
    shops_value = "false" if shops_enabled else "true"

    referral_text = "❌ Выключить реферальную систему" if referral_enabled else "✅ Включить реферальную систему"
    referral_value = "false" if referral_enabled else "true"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=shops_text, callback_data=f"admin:settings:shops:{shops_value}")],
        [InlineKeyboardButton(text=referral_text, callback_data=f"admin:settings:referral:{referral_value}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")],
    ])
