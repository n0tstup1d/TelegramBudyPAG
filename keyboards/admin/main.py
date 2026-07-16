from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="🧾 Чеки", callback_data="admin:receipts")],
        [InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="admin:withdrawals")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="admin:referral")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="👤 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin:promo")],
        [InlineKeyboardButton(text="🏪 Магазины", callback_data="admin:shops")],
        [InlineKeyboardButton(text="⚙️ Настройки проекта", callback_data="admin:settings")],
    ])


def admin_back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")]
    ])
