from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from aiogram import Bot
from sqlalchemy import select

from config import (
    PROJECT_NAME,
    TEAM_CHAT_ID,
    YOOKASSA_POLL_BATCH_SIZE,
    YOOKASSA_POLL_INTERVAL_SECONDS,
)
from database.engine import async_session
from database.models import Transaction, User
from keyboards.admin.receipts import receipt_team_notification_menu
from keyboards.common import bottom_keyboard
from services.receipts import RECEIPT_NOT_REQUIRED, ensure_receipt_pending
from services.yookassa import YooKassaError, amount_value, get_payment

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaymentProcessingResult:
    payment_id: str
    status: str
    paid: bool
    access_granted: bool = False
    already_processed: bool = False
    confirmation_url: str = ""


def _payment_amount_matches(payment: dict, expected_amount: int) -> bool:
    amount = payment.get("amount") or {}
    try:
        value = Decimal(str(amount.get("value")))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return value == Decimal(amount_value(expected_amount)) and amount.get("currency") == "RUB"


def _metadata_user_id(payment: dict) -> int | None:
    metadata = payment.get("metadata") or {}
    try:
        return int(metadata.get("telegram_user_id"))
    except (TypeError, ValueError):
        return None


def _confirmation_url(payment: dict) -> str:
    confirmation = payment.get("confirmation") or {}
    return str(confirmation.get("confirmation_url") or "").strip()


async def process_payment(
    *,
    bot: Bot,
    payment_id: str,
    expected_user_id: int | None = None,
    notify_user: bool = True,
) -> PaymentProcessingResult:
    """Проверяет платеж через API ЮKassa и идемпотентно выдаёт доступ."""
    payment = await get_payment(payment_id)
    api_status = str(payment.get("status") or "unknown")
    api_paid = bool(payment.get("paid"))
    confirmation_url = _confirmation_url(payment)

    async with async_session() as session:
        transaction = (
            await session.execute(
                select(Transaction)
                .where(Transaction.payment_id == payment_id)
                .order_by(Transaction.id.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()

        if transaction is None:
            logger.warning("Payment %s exists in YooKassa but is missing in local DB", payment_id)
            return PaymentProcessingResult(payment_id, api_status, False, confirmation_url=confirmation_url)

        if expected_user_id is not None and transaction.user_id != expected_user_id:
            raise YooKassaError("Платёж принадлежит другому пользователю")

        if transaction.paid:
            # Защита от старых записей: любой успешный платёж должен попасть
            # в очередь ручного формирования чека.
            if transaction.receipt_status == RECEIPT_NOT_REQUIRED:
                await ensure_receipt_pending(transaction)
                await session.commit()
            return PaymentProcessingResult(
                payment_id,
                transaction.status or "succeeded",
                True,
                already_processed=True,
                confirmation_url=confirmation_url,
            )

        metadata = payment.get("metadata") or {}
        metadata_user_id = _metadata_user_id(payment)
        if metadata_user_id != transaction.user_id:
            raise YooKassaError("В платеже не совпадает Telegram ID покупателя")
        if metadata.get("product") != "vega_lifetime_access":
            raise YooKassaError("Платёж относится к другому продукту")
        if not _payment_amount_matches(payment, transaction.amount):
            raise YooKassaError("В платеже не совпадает сумма или валюта")

        transaction.status = api_status
        transaction.updated_at = datetime.now()

        if api_status != "succeeded" or not api_paid:
            await session.commit()
            return PaymentProcessingResult(
                payment_id,
                api_status,
                False,
                confirmation_url=confirmation_url,
            )

        user = (
            await session.execute(
                select(User).where(User.user_id == transaction.user_id).with_for_update()
            )
        ).scalar_one_or_none()
        if user is None:
            raise YooKassaError("Пользователь платежа не найден в базе")

        access_granted = not user.has_subscription
        user.has_subscription = True
        if user.subscription_date is None:
            user.subscription_date = datetime.now()

        transaction.paid = True
        transaction.status = "succeeded"
        transaction.updated_at = datetime.now()
        await ensure_receipt_pending(transaction)
        await session.commit()

        transaction_id = transaction.id
        user_id = user.user_id
        username = user.username
        paid_amount = transaction.amount

    if notify_user:
        try:
            await bot.send_message(
                user_id,
                "✅ <b>Оплата подтверждена</b>\n\n"
                f"Бессрочный доступ к {PROJECT_NAME} открыт. "
                "Подписки и повторных списаний нет.\n\n"
                "🧾 Чек будет сформирован и направлен вам отдельным сообщением "
                "после обработки платежа.\n\n"
                "Нажмите «🏠 Меню», чтобы перейти к материалам.",
                parse_mode="HTML",
                reply_markup=bottom_keyboard(),
            )
        except Exception:
            logger.exception("Failed to notify user %s about successful payment", user_id)

        try:
            username_text = f"@{username}" if username else "без username"
            await bot.send_message(
                TEAM_CHAT_ID,
                "💳 <b>Успешная оплата ЮKassa</b>\n\n"
                f"Пользователь: {username_text}\n"
                f"Telegram ID: <code>{user_id}</code>\n"
                f"Сумма: <b>{paid_amount} ₽</b>\n"
                f"Платёж: <code>{payment_id}</code>\n"
                f"Доступ: {'открыт' if access_granted else 'уже был активен'}\n"
                "Чек: <b>ожидает оформления</b>",
                parse_mode="HTML",
                reply_markup=receipt_team_notification_menu(transaction_id),
            )
        except Exception:
            logger.exception("Failed to notify team about successful payment %s", payment_id)

    return PaymentProcessingResult(
        payment_id,
        "succeeded",
        True,
        access_granted=access_granted,
        confirmation_url=confirmation_url,
    )


async def payment_reconciliation_loop(bot: Bot) -> None:
    """Фоновая проверка ожидающих платежей без обязательного публичного webhook."""
    logger.info(
        "YooKassa reconciliation started: interval=%ss, batch=%s",
        YOOKASSA_POLL_INTERVAL_SECONDS,
        YOOKASSA_POLL_BATCH_SIZE,
    )

    while True:
        try:
            async with async_session() as session:
                payment_ids = list(
                    (
                        await session.execute(
                            select(Transaction.payment_id)
                            .where(
                                Transaction.provider == "yookassa",
                                Transaction.paid.is_(False),
                                Transaction.status.in_(("pending", "waiting_for_capture", "unknown")),
                            )
                            .order_by(Transaction.created_at.asc())
                            .limit(YOOKASSA_POLL_BATCH_SIZE)
                        )
                    ).scalars()
                )

            for payment_id in payment_ids:
                try:
                    await process_payment(bot=bot, payment_id=payment_id)
                except YooKassaError as exc:
                    logger.warning("YooKassa payment %s check failed: %s", payment_id, exc)
                except Exception:
                    logger.exception("Unexpected payment processing failure: %s", payment_id)
                await asyncio.sleep(0.15)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("YooKassa reconciliation iteration failed")

        await asyncio.sleep(max(5, YOOKASSA_POLL_INTERVAL_SECONDS))
