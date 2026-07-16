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


def user_card_menu(
    user_id: int,
    has_subscription: bool,
    role: str,
    content_blocked: bool = False,
    has_payments: bool = False,
    latest_transaction_id: int | None = None,
    latest_payment_paid: bool = False,
) -> InlineKeyboardMarkup:
    buttons = []

    if has_payments:
        buttons.append([
            InlineKeyboardButton(
                text="🔄 Проверить последний платёж",
                callback_data=f"admin:payment_check:{user_id}",
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                text="📋 История платежей",
                callback_data=f"admin:payment_history:{user_id}",
            )
        ])
        if latest_transaction_id is not None and latest_payment_paid:
            buttons.append([
                InlineKeyboardButton(
                    text="🧾 Чек по последней оплате",
                    callback_data=f"admin:receipt:{latest_transaction_id}",
                )
            ])

    if has_subscription:
        buttons.append([InlineKeyboardButton(text="❌ Забрать доступ", callback_data=f"admin:sub_remove:{user_id}")])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="✅ Выдать доступ вручную",
                callback_data=f"admin:sub_confirm:{user_id}",
            )
        ])

    if content_blocked:
        buttons.append([
            InlineKeyboardButton(
                text="🛡 Снять защитную паузу",
                callback_data=f"admin:content_unblock:{user_id}",
            )
        ])

    buttons.append([InlineKeyboardButton(text="🎭 Изменить роль", callback_data=f"admin:role_change:{user_id}")])
    buttons.append([
        InlineKeyboardButton(
            text="🚫 Забанить" if role != "banned" else "✅ Разбанить",
            callback_data=f"admin:ban:{user_id}" if role != "banned" else f"admin:unban:{user_id}",
        )
    ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:users")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def manual_access_confirm_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, выдать доступ",
                callback_data=f"admin:sub_give:{user_id}",
            )
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:user_card:{user_id}")],
    ])


def payment_history_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Проверить последний платёж",
                callback_data=f"admin:payment_check:{user_id}",
            )
        ],
        [InlineKeyboardButton(text="⬅️ К пользователю", callback_data=f"admin:user_card:{user_id}")],
    ])


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
