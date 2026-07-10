from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from database.engine import async_session
from database.models import WithdrawalRequest, ReferralBalance
from database.crud import get_user
from handlers.admin.guards import is_admin

router = Router()


@router.callback_query(F.data == "admin:withdrawals")
async def admin_withdrawals(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(
            select(WithdrawalRequest)
            .where(WithdrawalRequest.status.in_(["pending", "processing"]))
            .order_by(WithdrawalRequest.requested_at)
        )
        requests = result.scalars().all()

        if not requests:
            await callback.message.edit_text(
                "✅ Заявок на вывод нет",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")]
                ])
            )
            await callback.answer()
            return

        buttons = []
        for req in requests:
            status_icon = "🟡" if req.status == "pending" else "🔵"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_icon} #{req.id} — {req.amount} ₽",
                    callback_data=f"admin:withdrawal:{req.id}"
                )
            ])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")])

        await callback.message.edit_text(
            "💸 Заявки на вывод:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:withdrawal:"))
async def admin_withdrawal_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    request_id = int(callback.data.split(":")[2])

    async with async_session() as session:
        request = await session.get(WithdrawalRequest, request_id)
        if not request:
            await callback.answer("Заявка не найдена", show_alert=True)
            return

        user = await get_user(session, request.user_id)
        username = f"@{user.username}" if user and user.username else str(request.user_id)

        status_text = {
            "pending": "🟡 Ожидает",
            "processing": f"🔵 В обработке у {request.taken_by}",
            "completed": "✅ Выполнена",
            "cancelled": "❌ Отменена"
        }.get(request.status, request.status)

        text = (
            f"💸 Заявка #{request.id}\n\n"
            f"👤 Пользователь: {username}\n"
            f"💰 Сумма: {request.amount} ₽\n"
            f"📅 Создана: {request.requested_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"Статус: {status_text}"
        )

        buttons = []
        if request.status == "pending":
            buttons.append([
                InlineKeyboardButton(
                    text="🔵 Взять в работу",
                    callback_data=f"admin:take:{request_id}"
                )
            ])
        elif request.status == "processing" and request.taken_by == callback.from_user.id:
            buttons.append([
                InlineKeyboardButton(
                    text="✅ Подтвердить перевод",
                    callback_data=f"admin:complete:{request_id}"
                )
            ])
            buttons.append([
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"admin:cancel_withdrawal:{request_id}"
                )
            ])

        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:withdrawals")])

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:take:"))
async def admin_take_withdrawal(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    request_id = int(callback.data.split(":")[2])

    async with async_session() as session:
        request = await session.get(WithdrawalRequest, request_id)

        if request.status != "pending":
            await callback.answer("Заявка уже взята в работу!", show_alert=True)
            return

        request.status = "processing"
        request.taken_by = callback.from_user.id
        await session.commit()

        await callback.answer("✅ Заявка взята в работу")
        await admin_withdrawal_detail(callback)


@router.callback_query(F.data.startswith("admin:complete:"))
async def admin_complete_withdrawal(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    request_id = int(callback.data.split(":")[2])

    async with async_session() as session:
        request = await session.get(WithdrawalRequest, request_id)

        if request.taken_by != callback.from_user.id:
            await callback.answer("Это не твоя заявка!", show_alert=True)
            return

        request.status = "completed"
        request.completed_at = datetime.now()

        # размораживаем и обнуляем
        result = await session.execute(
            select(ReferralBalance).where(ReferralBalance.user_id == request.user_id)
        )
        balance = result.scalar_one_or_none()
        if balance:
            balance.frozen = 0
        await session.commit()

        # уведомляем пользователя
        await callback.bot.send_message(
            request.user_id,
            f"✅ Деньги отправлены!\n\n"
            f"Сумма: {request.amount} ₽\n"
            f"Заявка #{request.id}\n\n"
            f"Если деньги не пришли — напиши в поддержку."
        )

    await callback.answer("✅ Перевод подтверждён")
    await callback.message.edit_text(
        "✅ Заявка выполнена, пользователь уведомлён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К заявкам", callback_data="admin:withdrawals")]
        ])
    )


@router.callback_query(F.data.startswith("admin:cancel_withdrawal:"))
async def admin_cancel_withdrawal(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    request_id = int(callback.data.split(":")[2])

    async with async_session() as session:
        request = await session.get(WithdrawalRequest, request_id)
        request.status = "cancelled"

        # возвращаем баланс
        result = await session.execute(
            select(ReferralBalance).where(ReferralBalance.user_id == request.user_id)
        )
        balance = result.scalar_one_or_none()
        if balance:
            balance.balance = balance.frozen
            balance.frozen = 0
        await session.commit()

        await callback.bot.send_message(
            request.user_id,
            f"❌ Заявка на вывод #{request.id} отменена.\n\n"
            f"Средства возвращены на баланс.\n"
            f"Если это ошибка — напиши в поддержку."
        )

    await callback.answer("Заявка отменена")
    await callback.message.edit_text(
        "❌ Заявка отменена, средства возвращены.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К заявкам", callback_data="admin:withdrawals")]
        ])
    )
