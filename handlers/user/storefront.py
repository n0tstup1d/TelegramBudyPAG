from __future__ import annotations

from html import escape
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.exceptions import TelegramBadRequest

from config import (
    BOT_PUBLIC_URL,
    OFFER_FILE,
    OFFER_URL,
    PAYMENTS_ENABLED,
    PRIVACY_FILE,
    PRIVACY_URL,
    PRODUCT_ACCESS_YEARS,
    PRODUCT_PRICE,
    PROJECT_NAME,
    SELLER_EMAIL,
    SELLER_FULL_NAME,
    SELLER_INN,
    SELLER_PHONE,
)
from keyboards.common import (
    PAYMENT_PENDING_TEXT,
    PRODUCT_CARD_TEXT,
    legal_back_keyboard,
    pay_keyboard,
    storefront_back_keyboard,
)

router = Router()

SELLER_TEXT = (
    "📞 <b>Реквизиты продавца и поддержка</b>\n\n"
    f"ФИО: <b>{escape(SELLER_FULL_NAME)}</b>\n"
    "Статус: плательщик налога на профессиональный доход (самозанятый)\n"
    f"ИНН: <code>{escape(SELLER_INN)}</code>\n"
    f"Телефон: <code>{escape(SELLER_PHONE)}</code>\n"
    f"Электронная почта: <code>{escape(SELLER_EMAIL)}</code>\n"
    f"Telegram-бот: {escape(BOT_PUBLIC_URL)}\n\n"
    "По вопросам покупки, доступа, возврата и обработки персональных данных можно обратиться в поддержку "
    "или по электронной почте."
)


async def _edit_or_answer(message: Message, text: str, reply_markup=None) -> None:
    """Редактирует экран, а если Telegram не позволяет — отправляет новое сообщение."""
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
        f"Срок доступа: <b>{PRODUCT_ACCESS_YEARS} лет</b>\n"
        "Подписки и повторных списаний нет.\n\n"
        "Магазин проходит активацию в Robokassa. Все условия покупки доступны по кнопкам ниже."
    )
    await _edit_or_answer(callback.message, text, pay_keyboard())


@router.callback_query(F.data == "store:checkout")
async def checkout_callback(callback: CallbackQuery):
    await callback.answer()

    if PAYMENTS_ENABLED:
        # Защитный экран: переменную нельзя включать до добавления настоящей интеграции Robokassa.
        text = (
            "⚠️ <b>Платёжный модуль ещё не настроен</b>\n\n"
            "PAYMENTS_ENABLED включён, но формирование и проверка платежей Robokassa пока не добавлены. "
            "Оплата не создавалась, деньги не списывались."
        )
        await _edit_or_answer(callback.message, text, storefront_back_keyboard())
        return

    await _edit_or_answer(callback.message, PAYMENT_PENDING_TEXT, storefront_back_keyboard())


@router.message(Command("buy"))
async def checkout_command(message: Message):
    await message.answer(PAYMENT_PENDING_TEXT, parse_mode="HTML", reply_markup=storefront_back_keyboard())


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
        await callback.message.answer(
            f"Публичная оферта: {OFFER_URL}",
            reply_markup=legal_back_keyboard(),
        )
        return

    await _send_legal_document(
        callback.message,
        OFFER_FILE,
        "📄 Публичная оферта VEGA. Документ доступен до оплаты.",
    )


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
        await callback.message.answer(
            f"Политика обработки персональных данных: {PRIVACY_URL}",
            reply_markup=legal_back_keyboard(),
        )
        return

    await _send_legal_document(
        callback.message,
        PRIVACY_FILE,
        "🔐 Политика обработки персональных данных VEGA. Документ доступен до оплаты.",
    )


@router.message(Command("privacy"))
async def privacy_command(message: Message):
    if PRIVACY_URL:
        await message.answer(
            f"Политика обработки персональных данных: {PRIVACY_URL}",
            reply_markup=legal_back_keyboard(),
        )
        return
    await _send_legal_document(message, PRIVACY_FILE, "🔐 Политика обработки персональных данных VEGA.")
