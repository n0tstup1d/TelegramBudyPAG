from __future__ import annotations

from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup


async def safe_callback_answer(callback: CallbackQuery, *args: Any, **kwargs: Any) -> None:
    """Отвечает на callback без падения, если Telegram уже закрыл query."""
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest:
        pass


async def safe_edit_or_send(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    **kwargs: Any,
):
    """Редактирует сообщение, а если Telegram не даёт — отправляет новое.

    Полезно после фото/медиа-сообщений и при старых callback, где `edit_text` может падать.
    """
    try:
        return await callback.message.edit_text(text, reply_markup=reply_markup, **kwargs)
    except TelegramBadRequest:
        return await callback.message.answer(text, reply_markup=reply_markup, **kwargs)
