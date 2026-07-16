from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def receipts_dashboard_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Ожидают чека", callback_data="admin:receipts:list:pending:0")],
        [InlineKeyboardButton(text="⚠️ Просроченные", callback_data="admin:receipts:list:overdue:0")],
        [InlineKeyboardButton(text="✅ Отправленные", callback_data="admin:receipts:list:sent:0")],
        [InlineKeyboardButton(text="🔎 Найти чек", callback_data="admin:receipts:search")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:receipts")],
        [InlineKeyboardButton(text="⬅️ В админку", callback_data="admin:menu")],
    ])


def receipts_list_menu(
    rows: list[tuple[int, str]],
    *,
    category: str,
    page: int,
    has_next: bool,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=label, callback_data=f"admin:receipt:{transaction_id}")]
        for transaction_id, label in rows
    ]

    navigation: list[InlineKeyboardButton] = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"admin:receipts:list:{category}:{page - 1}")
        )
    if has_next:
        navigation.append(
            InlineKeyboardButton(text="➡️", callback_data=f"admin:receipts:list:{category}:{page + 1}")
        )
    if navigation:
        buttons.append(navigation)

    buttons.append([InlineKeyboardButton(text="⬅️ К чекам", callback_data="admin:receipts")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def receipt_card_menu(
    transaction_id: int,
    *,
    user_id: int,
    status: str,
    has_payload: bool,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []

    if status in {"pending", "sending"}:
        buttons.extend([
            [InlineKeyboardButton(
                text="🔗 Добавить ссылку и отправить",
                callback_data=f"admin:receipt:add_link:{transaction_id}",
            )],
            [InlineKeyboardButton(
                text="🖼 Добавить фото / PDF и отправить",
                callback_data=f"admin:receipt:add_file:{transaction_id}",
            )],
            [InlineKeyboardButton(
                text="✅ Отметить отправленным вручную",
                callback_data=f"admin:receipt:manual:{transaction_id}",
            )],
        ])
    elif status == "sent":
        if has_payload:
            buttons.append([InlineKeyboardButton(
                text="📨 Отправить чек повторно",
                callback_data=f"admin:receipt:resend:{transaction_id}",
            )])
        buttons.append([InlineKeyboardButton(
            text="🔄 Заменить ссылку / файл",
            callback_data=f"admin:receipt:add_link:{transaction_id}",
        )])
        buttons.append([InlineKeyboardButton(
            text="🖼 Заменить на фото / PDF",
            callback_data=f"admin:receipt:add_file:{transaction_id}",
        )])

    buttons.extend([
        [InlineKeyboardButton(
            text="👤 Открыть пользователя",
            callback_data=f"admin:user_card:{user_id}",
        )],
        [InlineKeyboardButton(text="⬅️ К ожидающим", callback_data="admin:receipts:list:pending:0")],
        [InlineKeyboardButton(text="🏠 Раздел чеков", callback_data="admin:receipts")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def receipt_cancel_menu(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:receipt:cancel:{transaction_id}")],
    ])


def receipt_send_confirm_menu(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Отправить покупателю", callback_data=f"admin:receipt:send:{transaction_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:receipt:cancel:{transaction_id}")],
    ])


def receipt_resend_confirm_menu(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Да, отправить повторно", callback_data=f"admin:receipt:resend_confirm:{transaction_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:receipt:{transaction_id}")],
    ])


def receipt_manual_confirm_menu(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, чек уже передан", callback_data=f"admin:receipt:manual_confirm:{transaction_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:receipt:{transaction_id}")],
    ])


def receipt_team_notification_menu(transaction_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧾 Оформить чек", callback_data=f"admin:receipt:{transaction_id}")],
        [InlineKeyboardButton(text="📋 Все ожидающие", callback_data="admin:receipts:list:pending:0")],
    ])
