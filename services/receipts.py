from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from urllib.parse import urlparse

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from config import (
    PROJECT_NAME,
    RECEIPT_FIRST_REMINDER_HOURS,
    RECEIPT_OVERDUE_HOURS,
    RECEIPT_REMINDER_INTERVAL_SECONDS,
    RECEIPT_URGENT_REMINDER_HOURS,
    TEAM_CHAT_ID,
)
from database.engine import async_session
from database.models import Transaction, User
from keyboards.admin.receipts import receipt_team_notification_menu

logger = logging.getLogger(__name__)

RECEIPT_NOT_REQUIRED = "not_required"
RECEIPT_PENDING = "pending"
RECEIPT_SENDING = "sending"
RECEIPT_SENT = "sent"


class ReceiptError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReceiptDeliveryResult:
    transaction_id: int
    user_id: int
    delivery_method: str
    sent_at: datetime


def validate_receipt_url(value: str) -> str:
    """Проверяет ссылку перед отправкой покупателю.

    Не привязываемся к одному домену ФНС, потому что формат ссылок приложения
    может меняться. Администратор всё равно видит ссылку на экране подтверждения.
    """
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ReceiptError("Нужна полная HTTPS-ссылка на чек")
    if len(url) > 1024:
        raise ReceiptError("Ссылка слишком длинная")
    return url


def receipt_reference_time(transaction: Transaction) -> datetime:
    return transaction.updated_at or transaction.created_at or datetime.now()


def receipt_age_hours(transaction: Transaction, *, now: datetime | None = None) -> float:
    current = now or datetime.now()
    return max(0.0, (current - receipt_reference_time(transaction)).total_seconds() / 3600)


def receipt_status_text(status: str | None) -> str:
    return {
        RECEIPT_NOT_REQUIRED: "— не требуется",
        RECEIPT_PENDING: "⏳ ожидает оформления",
        RECEIPT_SENDING: "📨 отправляется",
        RECEIPT_SENT: "✅ отправлен",
    }.get(status or "", f"❔ {status or 'неизвестно'}")


def receipt_delivery_text(method: str | None) -> str:
    return {
        "link": "ссылка",
        "photo": "изображение",
        "document": "файл / PDF",
        "manual": "передан вручную",
    }.get(method or "", "—")


def _receipt_caption(amount: int) -> str:
    return (
        "🧾 <b>Ваш чек</b>\n\n"
        f"Чек по оплате бессрочного доступа к {escape(PROJECT_NAME)} на сумму "
        f"<b>{amount} ₽</b>.\n\n"
        "Сохраните его при необходимости."
    )


async def ensure_receipt_pending(transaction: Transaction) -> None:
    if transaction.receipt_status in {RECEIPT_SENT, RECEIPT_SENDING, RECEIPT_PENDING}:
        return
    transaction.receipt_status = RECEIPT_PENDING
    transaction.receipt_reminder_level = 0
    transaction.receipt_updated_at = datetime.now()


async def deliver_receipt(
    *,
    bot: Bot,
    transaction_id: int,
    admin_id: int,
    receipt_url: str | None = None,
    receipt_file_id: str | None = None,
    receipt_file_type: str | None = None,
    use_stored_payload: bool = False,
) -> ReceiptDeliveryResult:
    """Отправляет чек покупателю и фиксирует результат.

    Чек уже должен быть создан администратором в «Мой налог». Бот лишь
    доставляет ссылку или загруженный файл нужному покупателю.
    """
    async with async_session() as session:
        transaction = (
            await session.execute(
                select(Transaction)
                .where(Transaction.id == transaction_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if transaction is None:
            raise ReceiptError("Платёж не найден")
        if not transaction.paid or transaction.status != "succeeded":
            raise ReceiptError("Чек можно отправить только по подтверждённому платежу")
        if transaction.receipt_status == RECEIPT_SENDING:
            raise ReceiptError("Этот чек уже отправляется другим администратором")

        if use_stored_payload:
            receipt_url = transaction.receipt_url
            receipt_file_id = transaction.receipt_file_id
            receipt_file_type = transaction.receipt_file_type

        if receipt_url:
            receipt_url = validate_receipt_url(receipt_url)
            delivery_method = "link"
            receipt_file_id = None
            receipt_file_type = None
        elif receipt_file_id and receipt_file_type in {"photo", "document"}:
            delivery_method = receipt_file_type
            receipt_url = None
        else:
            raise ReceiptError("Добавьте ссылку, изображение или PDF чека")

        user_id = transaction.user_id
        amount = transaction.amount
        previous_snapshot = {
            "receipt_status": transaction.receipt_status,
            "receipt_url": transaction.receipt_url,
            "receipt_file_id": transaction.receipt_file_id,
            "receipt_file_type": transaction.receipt_file_type,
            "receipt_delivery_method": transaction.receipt_delivery_method,
            "receipt_sent_at": transaction.receipt_sent_at,
            "receipt_admin_id": transaction.receipt_admin_id,
            "receipt_reminder_level": transaction.receipt_reminder_level,
        }
        transaction.receipt_status = RECEIPT_SENDING
        transaction.receipt_url = receipt_url
        transaction.receipt_file_id = receipt_file_id
        transaction.receipt_file_type = receipt_file_type
        transaction.receipt_delivery_method = delivery_method
        transaction.receipt_admin_id = admin_id
        transaction.receipt_updated_at = datetime.now()
        await session.commit()

    try:
        caption = _receipt_caption(amount)
        if delivery_method == "link":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧾 Открыть чек", url=receipt_url)],
            ])
            await bot.send_message(
                user_id,
                caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        elif delivery_method == "photo":
            await bot.send_photo(
                user_id,
                photo=receipt_file_id,
                caption=caption,
                parse_mode="HTML",
            )
        else:
            await bot.send_document(
                user_id,
                document=receipt_file_id,
                caption=caption,
                parse_mode="HTML",
            )
    except Exception as exc:
        async with async_session() as session:
            transaction = await session.get(Transaction, transaction_id)
            if transaction:
                for field, value in previous_snapshot.items():
                    setattr(transaction, field, value)
                if transaction.receipt_status not in {RECEIPT_PENDING, RECEIPT_SENT}:
                    transaction.receipt_status = RECEIPT_PENDING
                transaction.receipt_updated_at = datetime.now()
                await session.commit()
        raise ReceiptError(f"Telegram не смог отправить чек: {exc}") from exc

    sent_at = datetime.now()
    async with async_session() as session:
        transaction = await session.get(Transaction, transaction_id)
        if transaction is None:
            raise ReceiptError("Платёж исчез из базы после отправки")
        transaction.receipt_status = RECEIPT_SENT
        transaction.receipt_sent_at = sent_at
        transaction.receipt_admin_id = admin_id
        transaction.receipt_reminder_level = 3
        transaction.receipt_updated_at = sent_at
        await session.commit()

    return ReceiptDeliveryResult(
        transaction_id=transaction_id,
        user_id=user_id,
        delivery_method=delivery_method,
        sent_at=sent_at,
    )


async def mark_receipt_sent_manually(*, transaction_id: int, admin_id: int) -> None:
    async with async_session() as session:
        transaction = (
            await session.execute(
                select(Transaction)
                .where(Transaction.id == transaction_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if transaction is None:
            raise ReceiptError("Платёж не найден")
        if not transaction.paid or transaction.status != "succeeded":
            raise ReceiptError("Платёж ещё не подтверждён")

        now = datetime.now()
        transaction.receipt_status = RECEIPT_SENT
        transaction.receipt_delivery_method = "manual"
        transaction.receipt_sent_at = now
        transaction.receipt_admin_id = admin_id
        transaction.receipt_reminder_level = 3
        transaction.receipt_updated_at = now
        await session.commit()


def _reminder_level_for_age(age_hours: float) -> int:
    if age_hours >= RECEIPT_OVERDUE_HOURS:
        return 3
    if age_hours >= RECEIPT_URGENT_REMINDER_HOURS:
        return 2
    if age_hours >= RECEIPT_FIRST_REMINDER_HOURS:
        return 1
    return 0


def _reminder_title(level: int) -> str:
    if level >= 3:
        return f"🚨 Чек не отправлен более {RECEIPT_OVERDUE_HOURS} часов"
    if level == 2:
        return f"⚠️ Чек ожидает оформления более {RECEIPT_URGENT_REMINDER_HOURS} часов"
    return "🧾 Напоминание: оформите чек"


async def receipt_reminder_loop(bot: Bot) -> None:
    logger.info(
        "Receipt reminder loop started: interval=%ss, levels=%sh/%sh/%sh",
        RECEIPT_REMINDER_INTERVAL_SECONDS,
        RECEIPT_FIRST_REMINDER_HOURS,
        RECEIPT_URGENT_REMINDER_HOURS,
        RECEIPT_OVERDUE_HOURS,
    )

    while True:
        try:
            now = datetime.now()
            async with async_session() as session:
                # После аварийного завершения возвращаем зависшие отправки в очередь.
                stuck = list(
                    (
                        await session.execute(
                            select(Transaction).where(
                                Transaction.receipt_status == RECEIPT_SENDING,
                                Transaction.receipt_updated_at < now - timedelta(minutes=10),
                            )
                        )
                    ).scalars()
                )
                for transaction in stuck:
                    transaction.receipt_status = RECEIPT_PENDING
                    transaction.receipt_updated_at = now

                rows = list(
                    (
                        await session.execute(
                            select(Transaction, User)
                            .join(User, User.user_id == Transaction.user_id)
                            .where(
                                Transaction.paid.is_(True),
                                Transaction.status == "succeeded",
                                Transaction.receipt_status == RECEIPT_PENDING,
                            )
                            .order_by(Transaction.updated_at.asc(), Transaction.id.asc())
                            .limit(100)
                        )
                    ).all()
                )

                reminders: list[tuple[int, int, str, int, int, float]] = []
                for transaction, user in rows:
                    age = receipt_age_hours(transaction, now=now)
                    target_level = _reminder_level_for_age(age)
                    if target_level <= int(transaction.receipt_reminder_level or 0):
                        continue
                    transaction.receipt_reminder_level = target_level
                    transaction.receipt_updated_at = now
                    username = f"@{user.username}" if user.username else user.full_name
                    reminders.append(
                        (
                            transaction.id,
                            target_level,
                            username,
                            transaction.user_id,
                            transaction.amount,
                            age,
                        )
                    )
                await session.commit()

            for transaction_id, level, username, user_id, amount, age in reminders:
                try:
                    await bot.send_message(
                        TEAM_CHAT_ID,
                        f"{_reminder_title(level)}\n\n"
                        f"Покупатель: {escape(username)}\n"
                        f"Telegram ID: <code>{user_id}</code>\n"
                        f"Сумма: <b>{amount} ₽</b>\n"
                        f"Ожидает: <b>{age:.1f} ч.</b>",
                        parse_mode="HTML",
                        reply_markup=receipt_team_notification_menu(transaction_id),
                    )
                except Exception:
                    logger.exception("Failed to send receipt reminder for transaction %s", transaction_id)
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Receipt reminder iteration failed")

        await asyncio.sleep(max(60, RECEIPT_REMINDER_INTERVAL_SECONDS))
