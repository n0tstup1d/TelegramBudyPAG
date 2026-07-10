from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


STATS_PAGES = {
    "overview": "📊 Обзор",
    "users": "👥 Пользователи",
    "finance": "💳 Подписки/деньги",
    "referral": "👥 Рефералка",
    "withdrawals": "💸 Выводы",
    "shops": "🏪 Магазины",
    "promos": "🎟 Промокоды",
    "content": "📚 Контент",
}


def stats_menu(active: str = "overview") -> InlineKeyboardMarkup:
    buttons = []

    rows = [
        [("overview", STATS_PAGES["overview"]), ("users", STATS_PAGES["users"])],
        [("finance", STATS_PAGES["finance"]), ("referral", STATS_PAGES["referral"])],
        [("withdrawals", STATS_PAGES["withdrawals"]), ("shops", STATS_PAGES["shops"])],
        [("promos", STATS_PAGES["promos"]), ("content", STATS_PAGES["content"])],
    ]

    for row in rows:
        buttons.append([
            InlineKeyboardButton(
                text=("✅ " if page_id == active else "") + title,
                callback_data=f"admin:stats:{page_id}",
            )
            for page_id, title in row
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ В админку", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
