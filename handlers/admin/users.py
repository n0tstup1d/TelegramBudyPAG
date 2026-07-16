from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from database.crud import get_user
from database.engine import async_session
from database.models import ContentProtectionState, ContentStat, Transaction, User
from handlers.admin.guards import is_admin, is_superadmin
from keyboards.admin.users import (
    find_user_menu,
    manual_access_confirm_menu,
    payment_history_menu,
    role_menu,
    user_card_menu,
    users_list_menu,
    users_menu,
)
from services.content_protection import clear_content_block, make_license_code
from services.payments import process_payment
from services.receipts import receipt_status_text
from services.yookassa import YooKassaError
from states.admin import AdminUserStates

router = Router()


_PAYMENT_STATUS_LABELS = {
    "pending": "⏳ ожидает оплаты",
    "waiting_for_capture": "⏳ ожидает подтверждения",
    "succeeded": "✅ успешно",
    "canceled": "❌ отменён",
    "unknown": "❔ неизвестен",
}


def _payment_status_text(status: str | None, paid: bool) -> str:
    if paid:
        return "✅ успешно"
    normalized = (status or "unknown").strip().lower()
    return _PAYMENT_STATUS_LABELS.get(normalized, f"❔ {normalized}")


def _format_dt(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y %H:%M:%S") if value else "—"


async def _get_user(user_id: int) -> User | None:
    async with async_session() as session:
        return await get_user(session, user_id)


async def _get_latest_transaction(user_id: int) -> Transaction | None:
    async with async_session() as session:
        return (
            await session.execute(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.created_at.desc(), Transaction.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()


@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "👤 Управление пользователями",
        reply_markup=users_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:user_find")
async def admin_user_find(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(AdminUserStates.waiting_user_id)
    await state.update_data(mode="find")
    await callback.message.edit_text(
        "🔍 Введи username (@username) или Telegram ID:",
        reply_markup=find_user_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:role_find")
async def admin_role_find(callback: CallbackQuery, state: FSMContext):
    if not await is_superadmin(callback.from_user.id):
        await callback.answer("Только главный админ может менять роли", show_alert=True)
        return

    await state.set_state(AdminUserStates.waiting_user_id)
    await state.update_data(mode="role_change")
    await callback.message.edit_text(
        "🎭 Назначить роль\n\n"
        "Введи username (@username) или Telegram ID пользователя:",
        reply_markup=find_user_menu(),
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_user_id)
async def admin_user_search(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    state_data = await state.get_data()
    mode = state_data.get("mode", "find")
    search = (message.text or "").strip().lstrip("@")

    async with async_session() as session:
        if search.isdigit():
            result = await session.execute(select(User).where(User.user_id == int(search)))
        else:
            result = await session.execute(select(User).where(User.username == search))
        user = result.scalar_one_or_none()

    await state.clear()

    if not user:
        await message.answer("❌ Пользователь не найден", reply_markup=find_user_menu())
        return

    if mode == "role_change":
        role_text = {
            "user": "👤 Пользователь",
            "moderator": "🛡 Модератор",
            "admin": "⚙️ Администратор",
            "banned": "🚫 Заблокирован",
        }.get(user.role, user.role)
        username = f"@{user.username}" if user.username else "нет"
        await message.answer(
            f"🎭 Назначить роль\n\n"
            f"ID: {user.user_id}\n"
            f"Username: {username}\n"
            f"Имя: {user.full_name}\n"
            f"Текущая роль: {role_text}",
            reply_markup=role_menu(user.user_id),
        )
        return

    await send_user_card(message, user)


async def send_user_card(event: Message | CallbackQuery, user: User):
    sub_status = "✅ Активна" if user.has_subscription else "❌ Не активна"
    role_text = {
        "user": "👤 Пользователь",
        "moderator": "🛡 Модератор",
        "admin": "⚙️ Администратор",
        "banned": "🚫 Заблокирован",
    }.get(user.role, user.role)

    created = user.created_at.strftime("%d.%m.%Y")
    username = f"@{user.username}" if user.username else "нет"
    now = datetime.now()

    async with async_session() as session:
        protection_state = await session.scalar(
            select(ContentProtectionState).where(ContentProtectionState.user_id == user.user_id)
        )
        views_hour = int(
            await session.scalar(
                select(func.count(ContentStat.id)).where(
                    ContentStat.user_id == user.user_id,
                    ContentStat.clicked_at >= now - timedelta(hours=1),
                )
            )
            or 0
        )
        latest_payment = (
            await session.execute(
                select(Transaction)
                .where(Transaction.user_id == user.user_id)
                .order_by(Transaction.created_at.desc(), Transaction.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    content_blocked = bool(
        protection_state
        and protection_state.blocked_until
        and protection_state.blocked_until > now
    )
    if content_blocked:
        protection_text = f"⏳ до {protection_state.blocked_until:%d.%m.%Y %H:%M:%S}"
    else:
        protection_text = "✅ ограничений нет"

    warning_count = int(protection_state.warning_count or 0) if protection_state else 0
    last_reason = protection_state.last_reason if protection_state and protection_state.last_reason else "—"

    if latest_payment:
        payment_text = (
            "\n\n💳 Последний платёж\n"
            f"Сумма: {latest_payment.amount} ₽\n"
            f"Статус: {_payment_status_text(latest_payment.status, latest_payment.paid)}\n"
            f"Создан: {_format_dt(latest_payment.created_at)}\n"
            f"Проверен: {_format_dt(latest_payment.updated_at)}\n"
            f"ID платежа: {latest_payment.payment_id}\n"
            f"Чек: {receipt_status_text(latest_payment.receipt_status)}"
        )
    else:
        payment_text = "\n\n💳 Платежи\nПлатежей в базе нет"

    text = (
        "👤 Пользователь\n\n"
        f"ID: {user.user_id}\n"
        f"Username: {username}\n"
        f"Имя: {user.full_name}\n"
        f"Роль: {role_text}\n"
        f"Доступ: {sub_status}\n"
        f"Дата регистрации: {created}"
        f"{payment_text}\n\n"
        "🛡 Защита контента\n"
        f"Код лицензии: {make_license_code(user.user_id)}\n"
        f"Открытий за час: {views_hour}\n"
        f"Защитная пауза: {protection_text}\n"
        f"Срабатываний: {warning_count}\n"
        f"Последняя причина: {last_reason}"
    )

    keyboard = user_card_menu(
        user.user_id,
        user.has_subscription,
        user.role,
        content_blocked=content_blocked,
        has_payments=latest_payment is not None,
        latest_transaction_id=latest_payment.id if latest_payment else None,
        latest_payment_paid=bool(latest_payment and latest_payment.paid),
    )

    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard)
        return

    try:
        await event.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


@router.callback_query(F.data.startswith("admin:payment_check:"))
async def admin_payment_check(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[2])
    transaction = await _get_latest_transaction(user_id)
    if transaction is None:
        await callback.answer("У пользователя нет платежей в базе", show_alert=True)
        return

    await callback.answer("Проверяю платёж в ЮKassa…")
    try:
        result = await process_payment(
            bot=callback.bot,
            payment_id=transaction.payment_id,
            expected_user_id=user_id,
            notify_user=True,
        )
    except YooKassaError as exc:
        await callback.message.answer(
            "⚠️ Не удалось проверить платёж в ЮKassa.\n\n"
            f"Причина: {exc}\n"
            "Повторите проверку позже. Доступ по одному скриншоту не выдавайте."
        )
        return

    if result.paid:
        status_message = (
            "✅ Платёж подтверждён. Доступ открыт."
            if not result.already_processed
            else "✅ Платёж уже был подтверждён, доступ активен."
        )
    elif result.status == "canceled":
        status_message = "❌ ЮKassa сообщает, что платёж отменён."
    else:
        status_message = (
            f"⏳ Платёж пока не подтверждён. Статус ЮKassa: {result.status}. "
            "Повторная оплата без проверки не нужна."
        )

    await callback.message.answer(status_message)
    user = await _get_user(user_id)
    if user:
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:payment_history:"))
async def admin_payment_history(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        transactions = (
            await session.execute(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(Transaction.created_at.desc(), Transaction.id.desc())
                .limit(10)
            )
        ).scalars().all()

    if not transactions:
        await callback.answer("Платежей в базе нет", show_alert=True)
        return

    blocks = []
    for index, transaction in enumerate(transactions, start=1):
        blocks.append(
            f"{index}. {_format_dt(transaction.created_at)}\n"
            f"   {transaction.amount} ₽ · {_payment_status_text(transaction.status, transaction.paid)}\n"
            f"   Чек: {receipt_status_text(transaction.receipt_status)}\n"
            f"   {transaction.payment_id}"
        )

    await callback.message.edit_text(
        "📋 История платежей\n\n" + "\n\n".join(blocks),
        reply_markup=payment_history_menu(user_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:sub_confirm:"))
async def admin_sub_confirm(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        "⚠️ Выдать доступ вручную?\n\n"
        "Сначала используйте «Проверить последний платёж». "
        "Ручная выдача нужна только для подтверждённого исключения или подарочного доступа.",
        reply_markup=manual_access_confirm_menu(user_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:sub_give:"))
async def admin_sub_give(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.has_subscription = True
            if user.subscription_date is None:
                user.subscription_date = datetime.now()
            await session.commit()
    await callback.answer("✅ Доступ выдан вручную")
    user = await _get_user(user_id)
    if user:
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:sub_remove:"))
async def admin_sub_remove(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.has_subscription = False
            await session.commit()
    await callback.answer("❌ Доступ забран")
    user = await _get_user(user_id)
    if user:
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:content_unblock:"))
async def admin_content_unblock(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[2])
    await clear_content_block(user_id)
    await callback.answer("✅ Защитная пауза снята")

    user = await _get_user(user_id)
    if user:
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:role_change:"))
async def admin_role_change(callback: CallbackQuery):
    if not await is_superadmin(callback.from_user.id):
        await callback.answer("Только главный админ может менять роли", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    await callback.message.edit_text("🎭 Выбери новую роль:", reply_markup=role_menu(user_id))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:set_role:"))
async def admin_set_role(callback: CallbackQuery):
    if not await is_superadmin(callback.from_user.id):
        await callback.answer("Только главный админ может менять роли", show_alert=True)
        return
    parts = callback.data.split(":")
    user_id = int(parts[2])
    new_role = parts[3]
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.role = new_role
            await session.commit()
    await callback.answer("✅ Роль изменена")
    user = await _get_user(user_id)
    if user:
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:ban:"))
async def admin_ban(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.role = "banned"
            await session.commit()
    await callback.answer("🚫 Пользователь забанен")
    user = await _get_user(user_id)
    if user:
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:unban:"))
async def admin_unban(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.role = "user"
            await session.commit()
    await callback.answer("✅ Пользователь разбанен")
    user = await _get_user(user_id)
    if user:
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:users_list:"))
async def admin_users_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    category = parts[2]
    page = int(parts[3])
    limit = 10
    offset = page * limit

    async with async_session() as session:
        if category == "admins":
            query = select(User).where(User.role.in_(["admin", "moderator"]))
            count_query = select(func.count()).select_from(User).where(User.role.in_(["admin", "moderator"]))
            title = "⚙️ Администраторы"
        elif category == "banned":
            query = select(User).where(User.role == "banned")
            count_query = select(func.count()).select_from(User).where(User.role == "banned")
            title = "🚫 Забаненные"
        else:
            query = select(User)
            count_query = select(func.count()).select_from(User)
            title = "👥 Все пользователи"

        total = await session.scalar(count_query)
        result = await session.execute(query.offset(offset).limit(limit))
        users = result.scalars().all()

        if not users:
            await callback.message.edit_text(f"{title}\n\nПусто", reply_markup=users_menu())
            await callback.answer()
            return

        await callback.message.edit_text(
            f"{title}\n\nСтраница {page + 1} • Всего: {total}",
            reply_markup=users_list_menu(users, category, page, total),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user_card:"))
async def admin_user_card(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[2])
    user = await _get_user(user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    await send_user_card(callback, user)
    await callback.answer()
