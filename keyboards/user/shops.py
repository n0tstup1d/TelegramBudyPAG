from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def shops_menu(shops: list) -> InlineKeyboardMarkup:
    buttons = []
    for shop in shops:
        buttons.append([
            InlineKeyboardButton(text=f"🏪 {shop.name}", callback_data=f"shop:{shop.id}")
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shop_card_menu(shop_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Перейти в магазин", callback_data=f"shop_click:{shop_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="section:shops")],
    ])
