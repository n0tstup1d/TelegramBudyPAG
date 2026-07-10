from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def users_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin:users_list:all:0")],
        [InlineKeyboardButton(text="⚙️ Администраторы", callback_data="admin:users_list:admins:0")],
        [InlineKeyboardButton(text="🚫 Забаненные", callback_data="admin:users_list:banned:0")],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin:user_find")],
        [InlineKeyboardButton(text="🎭 Назначить роль", callback_data="admin:role_find")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")],
    ])


def users_list_menu(users: list, category: str, page: int, total: int) -> InlineKeyboardMarkup:
    buttons = []
    for user in users:
        username = f"@{user.username}" if user.username else user.full_name
        sub_icon = "💳" if user.has_subscription else "🆓"
        buttons.append([
            InlineKeyboardButton(text=f"{sub_icon} {username}", callback_data=f"admin:user_card:{user.user_id}")
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin:users_list:{category}:{page - 1}"))
    if (page + 1) * 10 < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin:users_list:{category}:{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:users")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_card_menu(user_id: int, has_subscription: bool, role: str) -> InlineKeyboardMarkup:
    buttons = []

    if has_subscription:
        buttons.append([InlineKeyboardButton(text="❌ Забрать подписку", callback_data=f"admin:sub_remove:{user_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="✅ Выдать подписку", callback_data=f"admin:sub_give:{user_id}")])

    buttons.append([InlineKeyboardButton(text="🎭 Изменить роль", callback_data=f"admin:role_change:{user_id}")])
    buttons.append([
        InlineKeyboardButton(
            text="🚫 Забанить" if role != "banned" else "✅ Разбанить",
            callback_data=f"admin:ban:{user_id}" if role != "banned" else f"admin:unban:{user_id}",
        )
    ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:users")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def role_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Пользователь", callback_data=f"admin:set_role:{user_id}:user")],
        [InlineKeyboardButton(text="🛡 Модератор", callback_data=f"admin:set_role:{user_id}:moderator")],
        [InlineKeyboardButton(text="⚙️ Администратор", callback_data=f"admin:set_role:{user_id}:admin")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:users")],
    ])


def find_user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Искать снова", callback_data="admin:user_find")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:users")],
    ])
