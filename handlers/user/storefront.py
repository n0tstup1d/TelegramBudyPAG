from __future__ import annotations

import asyncio
import logging
from html import escape
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy import select

from config import (
    BOT_PUBLIC_URL,
    OFFER_FILE,
    OFFER_URL,
    PAYMENTS_ENABLED,
    PRIVACY_FILE,
    PRIVACY_URL,
    PRODUCT_ACCESS_TEXT,
    PRODUCT_PRICE,
    PROJECT_NAME,
    SELLER_CITY,
    SELLER_EMAIL,
    SELLER_FULL_NAME,
    SELLER_INN,
    SELLER_LICENSE_INFO,
)
from database.engine import async_session
from database.models import Transaction, User
from keyboards.common import (
    PAYMENT_PENDING_TEXT,
    PRODUCT_CARD_TEXT,
    ROADMAP_TEXT,
    bottom_keyboard,
    documents_keyboard,
    legal_back_keyboard,
    pay_keyboard,
    roadmap_keyboard,
    storefront_back_keyboard,
    yookassa_checkout_keyboard,
)
from services.access_policy import has_access
from services.navigation import get_main_menu_markup
from services.payments import process_payment
from services.yookassa import YooKassaError, create_payment, get_payment, is_yookassa_configured

router = Router()
logger = logging.getLogger(__name__)
_user_checkout_locks: dict[int, asyncio.Lock] = {}

SELLER_TEXT = (
    "🏷 <b>Информация о поставщике</b>\n\n"
    f"ФИО: <b>{escape(SELLER_FULL_NAME)}</b>\n"
    f"Город: <b>{escape(SELLER_CITY)}</b>\n"
    "Статус: плательщик налога на профессиональный доход (самозанятый)\n"
    f"ИНН: <code>{escape(SELLER_INN)}</code>\n"
    f"Электронная почта: <code>{escape(SELLER_EMAIL)}</code>\n"
    f"Лицензия / аккредитация: {escape(SELLER_LICENSE_INFO)}\n"
    f"Telegram-бот: {escape(BOT_PUBLIC_URL)}\n\n"
    "По вопросам покупки, доступа, возврата и обработки персональных данных напишите в поддержку "
    "или на электронную почту. Контактный телефон поставщика указан в публичной оферте."
)


async def _edit_or_answer(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramBadRequest:
        await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)


async def _send_legal_document(message: Message, path: Path, caption: str) -> bool:
    if not path.exists() or not path.is_file():
        await message.answer(
            "⚠️ Документ временно недоступен. Сообщи об этом в поддержку.",
            reply_markup=legal_back_keyboard(),
        )
        return False

    await message.answer_document(
        document=FSInputFile(path),
        caption=caption,
        reply_markup=legal_back_keyboard(),
    )
    return True


def _checkout_lock(user_id: int) -> asyncio.Lock:
    lock = _user_checkout_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_checkout_locks[user_id] = lock
    return lock


async def _find_reusable_payment(user_id: int) -> tuple[str, str] | None:
    async with async_session() as session:
        transaction = (
            await session.execute(
                select(Transaction)
                .where(
                    Transaction.user_id == user_id,
                    Transaction.provider == "yookassa",
                    Transaction.paid.is_(False),
                    Transaction.status.in_(("pending", "unknown")),
                )
                .order_by(Transaction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if transaction is None:
        return None

    payment = await get_payment(transaction.payment_id)
    status = str(payment.get("status") or "unknown")
    confirmation = payment.get("confirmation") or {}
    payment_url = str(confirmation.get("confirmation_url") or "").strip()

    async with async_session() as session:
        current = (
            await session.execute(select(Transaction).where(Transaction.id == transaction.id))
        ).scalar_one_or_none()
        if current:
            current.status = status
            await session.commit()

    if status == "succeeded":
        return transaction.payment_id, "succeeded"
    if status == "pending" and payment_url:
        return transaction.payment_id, payment_url
    return None


async def _create_checkout(user_id: int) -> tuple[str, str]:
    reusable = await _find_reusable_payment(user_id)
    if reusable:
        payment_id, value = reusable
        if value == "succeeded":
            return payment_id, value
        return payment_id, value

    created = await create_payment(user_id=user_id)
    async with async_session() as session:
        session.add(
            Transaction(
                user_id=user_id,
                payment_id=created.payment_id,
                amount=PRODUCT_PRICE,
                paid=False,
                provider="yookassa",
                status=created.status,
            )
        )
        await session.commit()
    return created.payment_id, created.confirmation_url


async def _start_checkout(message: Message, user_id: int, *, edit: bool) -> None:
    if not PAYMENTS_ENABLED:
        if edit:
            await _edit_or_answer(message, PAYMENT_PENDING_TEXT, storefront_back_keyboard())
        else:
            await message.answer(PAYMENT_PENDING_TEXT, parse_mode="HTML", reply_markup=storefront_back_keyboard())
        return

    if not is_yookassa_configured():
        logger.error("PAYMENTS_ENABLED=true, but YooKassa credentials are missing")
        text = (
            "⚠️ <b>Оплата временно недоступна</b>\n\n"
            "Платёжный модуль не завершил настройку. Деньги не списывались. "
            "Обратитесь в поддержку или попробуйте позже."
        )
        if edit:
            await _edit_or_answer(message, text, storefront_back_keyboard())
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=storefront_back_keyboard())
        return

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.user_id == user_id))
        ).scalar_one_or_none()

    if user is None or not user.agreed_to_terms:
        text = "Сначала откройте /start, ознакомьтесь с офертой и подтвердите согласие."
        if edit:
            await _edit_or_answer(message, text, storefront_back_keyboard())
        else:
            await message.answer(text, reply_markup=storefront_back_keyboard())
        return

    if has_access(user):
        text = "✅ Доступ к VEGA уже активен. Повторная оплата не требуется."
        if edit:
            await _edit_or_answer(message, text)
        else:
            await message.answer(text)
        return

    async with _checkout_lock(user_id):
        try:
            payment_id, payment_url = await _create_checkout(user_id)
            if payment_url == "succeeded":
                result = await process_payment(bot=message.bot, payment_id=payment_id, expected_user_id=user_id)
                if result.paid:
                    await message.answer(
                        "✅ Оплата уже подтверждена. Бессрочный доступ открыт.\n\n"
                        "🧾 Чек будет сформирован и направлен вам отдельным сообщением "
                        "после обработки платежа.",
                        reply_markup=bottom_keyboard(),
                    )
                    await message.answer("Выберите направление:", reply_markup=await get_main_menu_markup())
                    return

            text = (
                "💳 <b>Платёж создан</b>\n\n"
                f"Продукт: бессрочный доступ к {escape(PROJECT_NAME)}\n"
                f"Сумма: <b>{PRODUCT_PRICE} ₽</b>\n"
                "Подписки и повторных списаний нет.\n\n"
                "🛡 <b>Защита материалов</b>\n"
                "Доступ предназначен одному пользователю для личного использования. Передача, "
                "публикация и перепродажа запрещены. Материалы защищены от штатной пересылки "
                "и содержат персональную лицензионную метку.\n\n"
                "<b>Как получить доступ:</b>\n"
                f"1. Нажмите «Оплатить {PRODUCT_PRICE} ₽» и завершите оплату.\n"
                "2. Вернитесь в бот.\n"
                "3. Нажмите «✅ Я оплатил — проверить».\n\n"
                "Обычно доступ открывается автоматически в течение 20–30 секунд. "
                "Повторно оплачивать не нужно.\n\n"
                "🧾 Чек будет сформирован и направлен вам отдельным сообщением "
                "после обработки платежа."
            )
            markup = yookassa_checkout_keyboard(payment_url, payment_id)
            if edit:
                await _edit_or_answer(message, text, markup)
            else:
                await message.answer(text, parse_mode="HTML", reply_markup=markup)
        except YooKassaError as exc:
            logger.warning("Failed to create YooKassa payment for %s: %s", user_id, exc)
            text = (
                "⚠️ <b>Не удалось создать платёж</b>\n\n"
                "Деньги не списывались. Попробуйте ещё раз через минуту или обратитесь в поддержку."
            )
            if edit:
                await _edit_or_answer(message, text, storefront_back_keyboard())
            else:
                await message.answer(text, parse_mode="HTML", reply_markup=storefront_back_keyboard())
        except Exception:
            logger.exception("Unexpected checkout failure for %s", user_id)
            text = "⚠️ Не удалось открыть оплату. Деньги не списывались. Попробуйте позже."
            if edit:
                await _edit_or_answer(message, text, storefront_back_keyboard())
            else:
                await message.answer(text, reply_markup=storefront_back_keyboard())


@router.callback_query(F.data == "store:product")
async def product_callback(callback: CallbackQuery):
    await callback.answer()
    await _edit_or_answer(callback.message, PRODUCT_CARD_TEXT, storefront_back_keyboard())


@router.message(Command("product"))
async def product_command(message: Message):
    await message.answer(PRODUCT_CARD_TEXT, parse_mode="HTML", reply_markup=storefront_back_keyboard())


@router.callback_query(F.data == "store:back")
async def storefront_back(callback: CallbackQuery):
    await callback.answer()
    text = (
        f"🔒 <b>Полный доступ к {escape(PROJECT_NAME)}</b>\n\n"
        f"Стоимость: <b>{PRODUCT_PRICE} ₽ единоразово</b>\n"
        f"Доступ: <b>{escape(PRODUCT_ACCESS_TEXT)}</b>\n"
        "Подписки и повторных списаний нет.\n\n"
        "📈 <b>VEGA развивается</b>\n"
        "База будет пополняться постепенно. В планах — психология, отношения и общение, "
        "мышление и развитие, обучение и навыки.\n\n"
        "🛡 Доступ предназначен для одного пользователя. Передача, массовое копирование, публикация "
        "и перепродажа материалов запрещены. Материалы содержат персональную лицензионную метку.\n\n"
        "До оплаты доступны описание продукта, документы, сведения о поставщике и поддержка."
    )
    await _edit_or_answer(callback.message, text, pay_keyboard())


@router.callback_query(F.data == "store:checkout")
async def checkout_callback(callback: CallbackQuery):
    await callback.answer("Готовлю платёж…")
    await _start_checkout(callback.message, callback.from_user.id, edit=True)


@router.message(Command("buy"))
async def checkout_command(message: Message):
    await _start_checkout(message, message.from_user.id, edit=False)


@router.callback_query(F.data.startswith("payment:check:"))
async def payment_check_callback(callback: CallbackQuery):
    await callback.answer("Проверяю оплату…")
    payment_id = (callback.data or "").removeprefix("payment:check:").strip()
    try:
        result = await process_payment(
            bot=callback.message.bot,
            payment_id=payment_id,
            expected_user_id=callback.from_user.id,
        )
    except YooKassaError as exc:
        logger.warning("Manual payment check failed for %s: %s", callback.from_user.id, exc)
        await _edit_or_answer(
            callback.message,
            "⚠️ Не удалось проверить платёж. Попробуйте ещё раз через минуту или обратитесь в поддержку.",
            storefront_back_keyboard(),
        )
        return

    if result.paid:
        await _edit_or_answer(
            callback.message,
            "✅ <b>Оплата подтверждена</b>\n\n"
            "Бессрочный доступ к VEGA открыт.\n\n"
            "🧾 Чек будет сформирован и направлен вам отдельным сообщением "
            "после обработки платежа.",
        )
        await callback.message.answer(
            "Главное меню доступно на клавиатуре внизу.",
            reply_markup=bottom_keyboard(),
        )
        await callback.message.answer("Выберите направление:", reply_markup=await get_main_menu_markup())
        return

    if result.status == "canceled":
        await _edit_or_answer(
            callback.message,
            "❌ Платёж отменён или истёк. Создайте новый платёж.",
            storefront_back_keyboard(),
        )
        return

    markup = (
        yookassa_checkout_keyboard(result.confirmation_url, payment_id)
        if result.confirmation_url
        else storefront_back_keyboard()
    )
    await _edit_or_answer(
        callback.message,
        "⏳ <b>Платёж пока обрабатывается</b>\n\nПодождите 10–20 секунд и нажмите «✅ Я оплатил — проверить» ещё раз. Повторная оплата не требуется.",
        markup,
    )


@router.callback_query(F.data == "store:roadmap")
async def roadmap_callback(callback: CallbackQuery):
    await callback.answer()
    await _edit_or_answer(callback.message, ROADMAP_TEXT, roadmap_keyboard())


@router.callback_query(F.data == "store:documents")
async def documents_callback(callback: CallbackQuery):
    await callback.answer()
    await _edit_or_answer(
        callback.message,
        "📄 <b>Документы и поддержка</b>\n\n"
        "Здесь доступны юридические документы, сведения о поставщике и связь с командой VEGA.",
        documents_keyboard(),
    )


@router.callback_query(F.data == "store:seller")
async def seller_callback(callback: CallbackQuery):
    await callback.answer()
    await _edit_or_answer(callback.message, SELLER_TEXT, storefront_back_keyboard())


@router.message(Command("seller"))
async def seller_command(message: Message):
    await message.answer(SELLER_TEXT, parse_mode="HTML", reply_markup=storefront_back_keyboard())


@router.callback_query(F.data == "legal:offer")
async def offer_callback(callback: CallbackQuery):
    await callback.answer("Открываю публичную оферту")
    if OFFER_URL:
        await callback.message.answer(f"Публичная оферта: {OFFER_URL}", reply_markup=legal_back_keyboard())
        return
    await _send_legal_document(callback.message, OFFER_FILE, "📄 Публичная оферта VEGA. Документ доступен до оплаты.")


@router.message(Command("offer"))
async def offer_command(message: Message):
    if OFFER_URL:
        await message.answer(f"Публичная оферта: {OFFER_URL}", reply_markup=legal_back_keyboard())
        return
    await _send_legal_document(message, OFFER_FILE, "📄 Публичная оферта VEGA.")


@router.callback_query(F.data == "legal:privacy")
async def privacy_callback(callback: CallbackQuery):
    await callback.answer("Открываю политику обработки данных")
    if PRIVACY_URL:
        await callback.message.answer(f"Политика обработки данных: {PRIVACY_URL}", reply_markup=legal_back_keyboard())
        return
    await _send_legal_document(callback.message, PRIVACY_FILE, "🔐 Политика обработки персональных данных VEGA.")


@router.message(Command("privacy"))
async def privacy_command(message: Message):
    if PRIVACY_URL:
        await message.answer(f"Политика обработки данных: {PRIVACY_URL}", reply_markup=legal_back_keyboard())
        return
    await _send_legal_document(message, PRIVACY_FILE, "🔐 Политика обработки персональных данных VEGA.")
