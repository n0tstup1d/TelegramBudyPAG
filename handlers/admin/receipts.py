from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, or_, select

from config import RECEIPT_ITEM_NAME, RECEIPT_OVERDUE_HOURS
from database.engine import async_session
from database.models import Transaction, User
from handlers.admin.guards import is_admin
from keyboards.admin.receipts import (
    receipt_cancel_menu,
    receipt_card_menu,
    receipt_manual_confirm_menu,
    receipt_resend_confirm_menu,
    receipt_send_confirm_menu,
    receipts_dashboard_menu,
    receipts_list_menu,
)
from services.receipts import (
    RECEIPT_PENDING,
    RECEIPT_SENDING,
    RECEIPT_SENT,
    ReceiptError,
    deliver_receipt,
    mark_receipt_sent_manually,
    receipt_age_hours,
    receipt_delivery_text,
    receipt_status_text,
    validate_receipt_url,
)
from states.admin import ReceiptStates

router = Router()
PAGE_SIZE = 10


def _format_dt(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y %H:%M:%S") if value else "—"


def _username(user: User) -> str:
    return f"@{user.username}" if user.username else user.full_name


async def _edit_or_answer(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramBadRequest:
        await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)


async def _get_transaction_user(transaction_id: int) -> tuple[Transaction, User] | None:
    async with async_session() as session:
        row = (
            await session.execute(
                select(Transaction, User)
                .join(User, User.user_id == Transaction.user_id)
                .where(Transaction.id == transaction_id)
            )
        ).first()
    if row is None:
        return None
    return row[0], row[1]


async def _show_receipt_card(event: CallbackQuery | Message, transaction_id: int) -> None:
    row = await _get_transaction_user(transaction_id)
    if row is None:
        text = "⚠️ Платёж не найден"
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return

    transaction, user = row
    age = receipt_age_hours(transaction)
    payload_text = "—"
    if transaction.receipt_url:
        payload_text = f"ссылка: {escape(transaction.receipt_url[:120])}"
    elif transaction.receipt_file_id:
        payload_text = receipt_delivery_text(transaction.receipt_file_type)

    text = (
        "🧾 <b>Чек по оплате</b>\n\n"
        f"Покупатель: <b>{escape(_username(user))}</b>\n"
        f"Telegram ID: <code>{user.user_id}</code>\n"
        f"Сумма: <b>{transaction.amount} ₽</b>\n"
        f"Наименование: {escape(RECEIPT_ITEM_NAME)}\n"
        f"Оплачено: {_format_dt(transaction.updated_at or transaction.created_at)}\n"
        f"Статус платежа: {'✅ подтверждён' if transaction.paid else '⏳ не подтверждён'}\n"
        f"Payment ID: <code>{escape(transaction.payment_id)}</code>\n\n"
        f"Статус чека: {receipt_status_text(transaction.receipt_status)}\n"
        f"Ожидает: {age:.1f} ч.\n"
        f"Способ: {receipt_delivery_text(transaction.receipt_delivery_method)}\n"
        f"Данные чека: {payload_text}\n"
        f"Отправлен: {_format_dt(transaction.receipt_sent_at)}\n"
        f"Администратор: {transaction.receipt_admin_id or '—'}"
    )
    markup = receipt_card_menu(
        transaction.id,
        user_id=user.user_id,
        status=transaction.receipt_status,
        has_payload=bool(transaction.receipt_url or transaction.receipt_file_id),
    )

    if isinstance(event, CallbackQuery):
        await _edit_or_answer(event.message, text, markup)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "admin:receipts")
async def receipts_dashboard(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    overdue_before = now - timedelta(hours=RECEIPT_OVERDUE_HOURS)

    async with async_session() as session:
        pending = int(
            await session.scalar(
                select(func.count(Transaction.id)).where(
                    Transaction.paid.is_(True),
                    Transaction.status == "succeeded",
                    Transaction.receipt_status.in_((RECEIPT_PENDING, RECEIPT_SENDING)),
                )
            )
            or 0
        )
        overdue = int(
            await session.scalar(
                select(func.count(Transaction.id)).where(
                    Transaction.paid.is_(True),
                    Transaction.status == "succeeded",
                    Transaction.receipt_status == RECEIPT_PENDING,
                    func.coalesce(Transaction.updated_at, Transaction.created_at) <= overdue_before,
                )
            )
            or 0
        )
        sent_today = int(
            await session.scalar(
                select(func.count(Transaction.id)).where(
                    Transaction.receipt_status == RECEIPT_SENT,
                    Transaction.receipt_sent_at >= today,
                )
            )
            or 0
        )

    text = (
        "🧾 <b>Чеки VEGA</b>\n\n"
        f"⏳ Ожидают оформления: <b>{pending}</b>\n"
        f"⚠️ Ожидают более {RECEIPT_OVERDUE_HOURS} часов: <b>{overdue}</b>\n"
        f"✅ Отправлены сегодня: <b>{sent_today}</b>\n\n"
        "Сначала сформируйте чек в приложении «Мой налог», затем добавьте сюда "
        "ссылку, изображение или PDF. Бот отправит чек нужному покупателю и сохранит историю."
    )
    await _edit_or_answer(callback.message, text, receipts_dashboard_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("admin:receipts:list:"))
async def receipts_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    parts = (callback.data or "").split(":")
    category = parts[3]
    try:
        page = max(0, int(parts[4]))
    except (IndexError, ValueError):
        page = 0

    now = datetime.now()
    overdue_before = now - timedelta(hours=RECEIPT_OVERDUE_HOURS)
    conditions = [Transaction.paid.is_(True), Transaction.status == "succeeded"]
    title = "Чеки"

    if category == "pending":
        conditions.append(Transaction.receipt_status.in_((RECEIPT_PENDING, RECEIPT_SENDING)))
        title = "⏳ Ожидают чека"
    elif category == "overdue":
        conditions.extend([
            Transaction.receipt_status == RECEIPT_PENDING,
            func.coalesce(Transaction.updated_at, Transaction.created_at) <= overdue_before,
        ])
        title = "⚠️ Просроченные чеки"
    elif category == "sent":
        conditions.append(Transaction.receipt_status == RECEIPT_SENT)
        title = "✅ Отправленные чеки"
    else:
        await callback.answer("Неизвестный раздел", show_alert=True)
        return

    async with async_session() as session:
        rows = list(
            (
                await session.execute(
                    select(Transaction, User)
                    .join(User, User.user_id == Transaction.user_id)
                    .where(*conditions)
                    .order_by(Transaction.updated_at.desc(), Transaction.id.desc())
                    .offset(page * PAGE_SIZE)
                    .limit(PAGE_SIZE + 1)
                )
            ).all()
        )

    has_next = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    keyboard_rows: list[tuple[int, str]] = []
    for transaction, user in rows:
        date_text = _format_dt(transaction.updated_at or transaction.created_at)[:10]
        label = f"{date_text} · {transaction.amount} ₽ · {_username(user)[:24]}"
        keyboard_rows.append((transaction.id, label))

    text = f"{title}\n\n"
    text += "Выберите платёж:" if keyboard_rows else "Здесь пока ничего нет."
    await _edit_or_answer(
        callback.message,
        text,
        receipts_list_menu(keyboard_rows, category=category, page=page, has_next=has_next),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:receipt:\d+$"))
async def receipt_card(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.clear()
    transaction_id = int((callback.data or "").split(":")[2])
    await _show_receipt_card(callback, transaction_id)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:receipt:add_link:"))
async def receipt_add_link(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    transaction_id = int((callback.data or "").split(":")[3])
    row = await _get_transaction_user(transaction_id)
    if row is None or not row[0].paid:
        await callback.answer("Подтверждённый платёж не найден", show_alert=True)
        return

    await state.set_state(ReceiptStates.waiting_link)
    await state.update_data(transaction_id=transaction_id)
    await _edit_or_answer(
        callback.message,
        "🔗 <b>Добавление чека по ссылке</b>\n\n"
        "1. Создайте чек в приложении «Мой налог».\n"
        "2. Нажмите «Отправить» и скопируйте ссылку.\n"
        "3. Пришлите ссылку сюда одним сообщением.\n\n"
        "Перед отправкой покупателю бот покажет подтверждение.",
        receipt_cancel_menu(transaction_id),
    )
    await callback.answer()


@router.message(ReceiptStates.waiting_link)
async def receipt_link_received(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    transaction_id = int(data.get("transaction_id") or 0)
    try:
        url = validate_receipt_url(message.text or "")
    except ReceiptError as exc:
        await message.answer(f"⚠️ {exc}\n\nПришлите полную HTTPS-ссылку.")
        return

    row = await _get_transaction_user(transaction_id)
    if row is None:
        await state.clear()
        await message.answer("⚠️ Платёж не найден")
        return
    transaction, user = row
    await state.set_state(ReceiptStates.confirming)
    await state.update_data(receipt_kind="link", receipt_url=url)
    await message.answer(
        "📨 <b>Проверьте перед отправкой</b>\n\n"
        f"Покупатель: <b>{escape(_username(user))}</b>\n"
        f"Telegram ID: <code>{user.user_id}</code>\n"
        f"Сумма: <b>{transaction.amount} ₽</b>\n"
        f"Ссылка: {escape(url)}\n\n"
        "Отправить этот чек покупателю?",
        parse_mode="HTML",
        reply_markup=receipt_send_confirm_menu(transaction_id),
    )


@router.callback_query(F.data.startswith("admin:receipt:add_file:"))
async def receipt_add_file(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    transaction_id = int((callback.data or "").split(":")[3])
    row = await _get_transaction_user(transaction_id)
    if row is None or not row[0].paid:
        await callback.answer("Подтверждённый платёж не найден", show_alert=True)
        return

    await state.set_state(ReceiptStates.waiting_file)
    await state.update_data(transaction_id=transaction_id)
    await _edit_or_answer(
        callback.message,
        "🖼 <b>Добавление файла чека</b>\n\n"
        "Пришлите изображение чека как фото либо PDF/изображение как документ. "
        "Бот сохранит Telegram file_id и отправит файл покупателю после подтверждения.",
        receipt_cancel_menu(transaction_id),
    )
    await callback.answer()


@router.message(ReceiptStates.waiting_file)
async def receipt_file_received(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    data = await state.get_data()
    transaction_id = int(data.get("transaction_id") or 0)

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    else:
        await message.answer("⚠️ Пришлите чек как фото или документ/PDF.")
        return

    row = await _get_transaction_user(transaction_id)
    if row is None:
        await state.clear()
        await message.answer("⚠️ Платёж не найден")
        return
    transaction, user = row
    await state.set_state(ReceiptStates.confirming)
    await state.update_data(
        receipt_kind="file",
        receipt_file_id=file_id,
        receipt_file_type=file_type,
    )
    await message.answer(
        "📨 <b>Проверьте перед отправкой</b>\n\n"
        f"Покупатель: <b>{escape(_username(user))}</b>\n"
        f"Telegram ID: <code>{user.user_id}</code>\n"
        f"Сумма: <b>{transaction.amount} ₽</b>\n"
        f"Формат: <b>{'изображение' if file_type == 'photo' else 'файл / PDF'}</b>\n\n"
        "Отправить этот чек покупателю?",
        parse_mode="HTML",
        reply_markup=receipt_send_confirm_menu(transaction_id),
    )


@router.callback_query(F.data.startswith("admin:receipt:send:"))
async def receipt_send(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    transaction_id = int((callback.data or "").split(":")[3])
    data = await state.get_data()
    if int(data.get("transaction_id") or 0) != transaction_id:
        await callback.answer("Сессия устарела. Откройте чек заново.", show_alert=True)
        return

    try:
        result = await deliver_receipt(
            bot=callback.bot,
            transaction_id=transaction_id,
            admin_id=callback.from_user.id,
            receipt_url=data.get("receipt_url"),
            receipt_file_id=data.get("receipt_file_id"),
            receipt_file_type=data.get("receipt_file_type"),
        )
    except ReceiptError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await state.clear()
    await callback.answer("✅ Чек отправлен")
    await callback.message.answer(
        f"✅ Чек отправлен покупателю {result.user_id}.\n"
        f"Способ: {receipt_delivery_text(result.delivery_method)}."
    )
    await _show_receipt_card(callback, transaction_id)


@router.callback_query(F.data.startswith("admin:receipt:resend:"))
async def receipt_resend_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    transaction_id = int((callback.data or "").split(":")[3])
    row = await _get_transaction_user(transaction_id)
    if row is None:
        await callback.answer("Платёж не найден", show_alert=True)
        return
    transaction, user = row
    if not (transaction.receipt_url or transaction.receipt_file_id):
        await callback.answer("У чека нет сохранённой ссылки или файла", show_alert=True)
        return
    await _edit_or_answer(
        callback.message,
        "📨 <b>Повторная отправка</b>\n\n"
        f"Покупатель: <b>{escape(_username(user))}</b>\n"
        f"Сумма: <b>{transaction.amount} ₽</b>\n\n"
        "Отправить ранее сохранённый чек ещё раз?",
        receipt_resend_confirm_menu(transaction_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:receipt:resend_confirm:"))
async def receipt_resend(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    transaction_id = int((callback.data or "").split(":")[3])
    try:
        await deliver_receipt(
            bot=callback.bot,
            transaction_id=transaction_id,
            admin_id=callback.from_user.id,
            use_stored_payload=True,
        )
    except ReceiptError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("✅ Чек отправлен повторно")
    await _show_receipt_card(callback, transaction_id)


@router.callback_query(F.data.startswith("admin:receipt:manual:"))
async def receipt_manual(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    transaction_id = int((callback.data or "").split(":")[3])
    await _edit_or_answer(
        callback.message,
        "✅ <b>Отметить чек отправленным вручную?</b>\n\n"
        "Используйте это только если вы уже передали чек покупателю вне бота. "
        "Бот не будет отправлять сообщение, но сохранит отметку в истории.",
        receipt_manual_confirm_menu(transaction_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:receipt:manual_confirm:"))
async def receipt_manual_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    transaction_id = int((callback.data or "").split(":")[3])
    try:
        await mark_receipt_sent_manually(
            transaction_id=transaction_id,
            admin_id=callback.from_user.id,
        )
    except ReceiptError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("✅ Отмечено")
    await _show_receipt_card(callback, transaction_id)


@router.callback_query(F.data.startswith("admin:receipt:cancel:"))
async def receipt_cancel(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    transaction_id = int((callback.data or "").split(":")[3])
    await state.clear()
    await callback.answer("Отменено")
    await _show_receipt_card(callback, transaction_id)


@router.callback_query(F.data == "admin:receipts:search")
async def receipt_search(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(ReceiptStates.waiting_search)
    await _edit_or_answer(
        callback.message,
        "🔎 <b>Поиск чека</b>\n\n"
        "Введите Telegram ID, @username, внутренний номер платежа или Payment ID.",
        receipts_dashboard_menu(),
    )
    await callback.answer()


@router.message(ReceiptStates.waiting_search)
async def receipt_search_value(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    if not value:
        await message.answer("Введите значение для поиска.")
        return

    async with async_session() as session:
        query = (
            select(Transaction, User)
            .join(User, User.user_id == Transaction.user_id)
            .where(Transaction.paid.is_(True), Transaction.status == "succeeded")
        )
        if value.startswith("@"):
            query = query.where(func.lower(User.username) == value[1:].lower())
        elif value.isdigit():
            number = int(value)
            query = query.where(or_(Transaction.user_id == number, Transaction.id == number))
        else:
            query = query.where(Transaction.payment_id.ilike(f"{value}%"))

        row = (
            await session.execute(
                query.order_by(Transaction.updated_at.desc(), Transaction.id.desc()).limit(1)
            )
        ).first()

    await state.clear()
    if row is None:
        await message.answer("Ничего не найдено.", reply_markup=receipts_dashboard_menu())
        return
    await _show_receipt_card(message, row[0].id)
