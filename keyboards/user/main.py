from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


SECTIONS = {
    "supplements": "💊 Добавки",
    "sleep": "💤 Сон",
    "nutrition": "🥗 Питание",
    "brain": "🧠 Концентрация и мозг",
    "recovery": "🏃 Восстановление",
    "analytics": "📊 Анализы и мониторинг",
}


def main_menu(referral_enabled: bool = False, shops_enabled: bool = False) -> InlineKeyboardMarkup:
    """Главное inline-меню: только продуктовый контент.

    Профиль, помощь и контакты вынесены в нижнюю reply-клавиатуру.
    `referral_enabled` оставлен для совместимости со старыми вызовами.
    `shops_enabled` управляет видимостью кнопки магазинов в пользовательском меню.
    """
    rows = [
        [
            InlineKeyboardButton(text="💤 Сон", callback_data="section:sleep"),
            InlineKeyboardButton(text="🥗 Питание", callback_data="section:nutrition"),
        ],
        [
            InlineKeyboardButton(text="🧠 Мозг и фокус", callback_data="section:brain"),
            InlineKeyboardButton(text="💊 Добавки", callback_data="section:supplements"),
        ],
        [InlineKeyboardButton(text="🏃 Восстановление", callback_data="section:recovery")],
        [InlineKeyboardButton(text="📊 Анализы и мониторинг", callback_data="section:analytics")],
    ]

    if shops_enabled:
        rows.append([InlineKeyboardButton(text="🏪 Магазины БАДов", callback_data="section:shops")])

    rows.append([InlineKeyboardButton(text="🗺 Развитие VEGA", callback_data="store:roadmap")])

    return InlineKeyboardMarkup(inline_keyboard=rows)
