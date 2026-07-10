from __future__ import annotations

import asyncio
import logging
from html import escape

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from database.engine import async_session
from database.models import User
from handlers.admin.guards import is_admin
from states.admin import BroadcastStates

router = Router()
logger = logging.getLogger(__name__)

BROADCAST_AUDIENCE = {"all", "paid", "free"}


def admin_broadcast_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")]
    ])


def broadcast_audience_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="broadcast:audience:all")],
        [InlineKeyboardButton(text="💳 Только подписчики", callback_data="broadcast:audience:paid")],
        [InlineKeyboardButton(text="🆓 Без подписки", callback_data="broadcast:audience:free")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")],
    ])


def yes_no_button_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="broadcast:add_button")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="broadcast:no_button")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")],
    ])


def build_url_keyboard(button_text: str | None, button_url: str | None) -> InlineKeyboardMarkup | None:
    if not button_text or not button_url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, url=button_url)]
    ])


def build_confirm_keyboard(button_text: str | None, button_url: str | None) -> InlineKeyboardMarkup:
    keyboard = []
    if button_text and button_url:
        keyboard.append([InlineKeyboardButton(text=button_text, url=button_url)])
    keyboard.append([InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast:send")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def safe_answer(callback: CallbackQuery, *args, **kwargs) -> None:
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest:
        pass


async def safe_edit_or_send(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    """Редактирует текущее сообщение, а если это фото/медиа — отправляет новое."""
    try:
        return await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        return await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await safe_answer(callback)
    await state.clear()
    await callback.message.edit_text(
        "📢 Рассылка\n\nВыбери аудиторию:",
        reply_markup=broadcast_audience_keyboard(),
    )


@router.callback_query(F.data == "broadcast:cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await safe_answer(callback, "Рассылка отменена")
    await state.clear()
    await safe_edit_or_send(
        callback,
        "📢 Рассылка отменена.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В админку", callback_data="admin:menu")]
        ]),
    )


@router.callback_query(F.data.startswith("broadcast:audience:"))
async def broadcast_audience(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await safe_answer(callback)

    audience = callback.data.split(":", 2)[2]
    if audience not in BROADCAST_AUDIENCE:
        await callback.message.edit_text(
            "⚠️ Неизвестная аудитория рассылки.",
            reply_markup=broadcast_audience_keyboard(),
        )
        return

    audience_text = {
        "all": "все пользователи",
        "paid": "только подписчики",
        "free": "без подписки",
    }[audience]

    await state.set_state(BroadcastStates.waiting_message)
    await state.update_data(audience=audience)

    await callback.message.edit_text(
        f"📢 Аудитория: {audience_text}\n\n"
        f"Отправь текст рассылки. Можно отправить фото с подписью — оно тоже уйдёт пользователям.",
        reply_markup=admin_broadcast_cancel_keyboard(),
    )


@router.message(BroadcastStates.waiting_message)
async def broadcast_message(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    text = message.text or message.caption or ""
    photo = message.photo[-1].file_id if message.photo else None

    if not text and not photo:
        await message.answer("⚠️ Отправь текст или фото для рассылки.")
        return

    await state.update_data(text=text, photo=photo)
    await state.set_state(BroadcastStates.waiting_button_decision)

    await message.answer(
        "Хочешь добавить кнопку-ссылку к сообщению?",
        reply_markup=yes_no_button_keyboard(),
    )


@router.callback_query(F.data == "broadcast:no_button")
async def broadcast_no_button(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await safe_answer(callback)
    await state.update_data(button_text=None, button_url=None)
    await show_broadcast_preview(callback, state)


@router.callback_query(F.data == "broadcast:add_button")
async def broadcast_add_button(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await safe_answer(callback)
    await state.set_state(BroadcastStates.waiting_button)
    await callback.message.edit_text(
        "Напиши текст кнопки и ссылку через символ |\n\n"
        "Например:\n"
        "Перейти на сайт | https://example.com",
        reply_markup=admin_broadcast_cancel_keyboard(),
    )


@router.message(BroadcastStates.waiting_button)
async def broadcast_button(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    try:
        parts = (message.text or "").split("|", 1)
        if len(parts) != 2:
            raise ValueError
        btn_text = parts[0].strip()
        btn_url = parts[1].strip()
        if not btn_text or not btn_url.startswith(("http://", "https://")):
            raise ValueError
        await state.update_data(button_text=btn_text, button_url=btn_url)
    except ValueError:
        await message.answer(
            "⚠️ Неверный формат. Используй:\n"
            "Текст кнопки | https://ссылка"
        )
        return

    await show_broadcast_preview(message, state)


async def show_broadcast_preview(event: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("text") or ""
    photo = data.get("photo")
    audience = data.get("audience")
    button_text = data.get("button_text")
    button_url = data.get("button_url")

    audience_text = {
        "all": "все пользователи",
        "paid": "только подписчики",
        "free": "без подписки",
    }.get(audience, "не выбрана")

    preview = f"📢 Предпросмотр рассылки\n\nАудитория: {audience_text}\n\n{text}".strip()
    keyboard = build_confirm_keyboard(button_text, button_url)

    if isinstance(event, CallbackQuery):
        if photo:
            await event.message.answer_photo(photo=photo, caption=preview, reply_markup=keyboard)
        else:
            await event.message.edit_text(preview, reply_markup=keyboard)
    else:
        if photo:
            await event.answer_photo(photo=photo, caption=preview, reply_markup=keyboard)
        else:
            await event.answer(preview, reply_markup=keyboard)

    await state.set_state(BroadcastStates.confirm)


@router.callback_query(F.data == "broadcast:send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await safe_answer(callback, "Рассылка запущена")

    data = await state.get_data()
    text = data.get("text") or ""
    photo = data.get("photo")
    audience = data.get("audience")
    button_text = data.get("button_text")
    button_url = data.get("button_url")
    keyboard = build_url_keyboard(button_text, button_url)

    if not text and not photo:
        await safe_edit_or_send(
            callback,
            "⚠️ Текст/фото рассылки не найден. Начни рассылку заново.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Новая рассылка", callback_data="admin:broadcast")],
                [InlineKeyboardButton(text="⬅️ В админку", callback_data="admin:menu")],
            ]),
        )
        await state.clear()
        return

    async with async_session() as session:
        query = select(User.user_id).where(User.role != "banned")
        if audience == "paid":
            query = query.where(User.has_subscription == True)
        elif audience == "free":
            query = query.where(User.has_subscription == False)

        result = await session.execute(query)
        user_ids = list(result.scalars().all())

    total = len(user_ids)
    status_message = await callback.message.answer(f"📢 Рассылка запущена... 0/{total}")

    success = 0
    failed = 0

    for index, user_id in enumerate(user_ids, start=1):
        try:
            if photo:
                await callback.bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=text or None,
                    reply_markup=keyboard,
                )
            else:
                await callback.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=keyboard,
                )
            success += 1
        except Exception as exc:
            failed += 1
            logger.warning("Broadcast failed for user %s: %s", user_id, exc)

        # Чуть разгружаем Telegram API и периодически обновляем прогресс.
        if index % 25 == 0 or index == total:
            try:
                await status_message.edit_text(
                    f"📢 Рассылка идёт... {index}/{total}\n"
                    f"✅ Успешно: {success}\n"
                    f"⚠️ Ошибок: {failed}"
                )
            except TelegramBadRequest:
                pass
            await asyncio.sleep(0.05)

    await state.clear()
    await status_message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"Получателей: {total}\n"
        f"Отправлено: {success}\n"
        f"Ошибок: {failed}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Новая рассылка", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="⬅️ В админку", callback_data="admin:menu")],
        ]),
    )
