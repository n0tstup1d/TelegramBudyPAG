from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def promo_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin:promo_create")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin:promo_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")],
    ])


def promo_list_menu(promos: list) -> InlineKeyboardMarkup:
    buttons = []
    for promo in promos:
        status = "✅" if promo.is_active else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {promo.code} — {promo.discount} ₽ ({promo.used_count}/{promo.usage_limit})",
                callback_data=f"admin:promo_card:{promo.id}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:promo")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def promo_card_menu(promo_id: int, is_active: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Выключить" if is_active else "✅ Включить",
            callback_data=f"admin:promo_toggle:{promo_id}",
        )],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:promo_delete:{promo_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:promo_list")],
    ])
