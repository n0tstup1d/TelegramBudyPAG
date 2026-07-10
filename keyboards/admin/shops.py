from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_shops_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить магазин", callback_data="admin:shop_add")],
        [InlineKeyboardButton(text="📋 Список магазинов", callback_data="admin:shop_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")],
    ])


def admin_shop_card_menu(shop_id: int, is_active: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Выключить" if is_active else "✅ Включить",
            callback_data=f"admin:shop_toggle:{shop_id}",
        )],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:shop_delete:{shop_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:shop_list")],
    ])
