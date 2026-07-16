from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from sqlalchemy import select
import logging
from html import escape

from database.crud import get_user, create_user, agree_to_terms
from database.engine import async_session
from database.models import Transaction, User
from database.settings import is_referral_enabled
from keyboards.common import (
    SUBSCRIPTION_REQUIRED_TEXT,
    terms_keyboard,
    pay_keyboard,
    banned_keyboard,
)
from utils.notifications import notify_new_user
from services.navigation import send_home, edit_home, send_support_center
from services.access import has_access
from services.payments import process_payment
from services.yookassa import YooKassaError
from config import (
    PRODUCT_PRICE, PRODUCT_ACCESS_TEXT, SELLER_FULL_NAME, SELLER_CITY,
    SELLER_INN, SELLER_EMAIL, SELLER_LICENSE_INFO,
)

router = Router()
logger = logging.getLogger(__name__)


async def _check_returned_payment(message: Message) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or args[1].strip() != "payment_return":
        return

    async with async_session() as session:
        payment_id = (
            await session.execute(
                select(Transaction.payment_id)
                .where(
                    Transaction.user_id == message.from_user.id,
                    Transaction.provider == "yookassa",
                    Transaction.paid.is_(False),
                )
                .order_by(Transaction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if not payment_id:
        return

    try:
        await process_payment(
            bot=message.bot,
            payment_id=payment_id,
            expected_user_id=message.from_user.id,
            notify_user=False,
        )
    except YooKassaError as exc:
        logger.info("Payment return check is not ready for %s: %s", message.from_user.id, exc)
    except Exception:
        logger.exception("Payment return check failed for %s", message.from_user.id)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await _check_returned_payment(message)
    async with async_session() as session:
        referred_by = None
        referral_enabled = await is_referral_enabled(session)
        args = message.text.split()
        if referral_enabled and len(args) > 1:
            ref_code = args[1].strip()
            if ref_code.startswith("ref_"):
                ref_code = ref_code[4:]

            result = await session.execute(
                select(User).where(User.referral_code == ref_code)
            )
            referrer = result.scalar_one_or_none()
            if referrer and referrer.user_id != message.from_user.id:
                referred_by = referrer.user_id

        user = await get_user(session, message.from_user.id)

        if user and user.role == "banned":
            await message.answer(
                "🚫 Ваш аккаунт заблокирован.\n\n"
                "Если считаете это ошибкой — обратитесь в поддержку.",
                reply_markup=banned_keyboard(),
            )
            return

        if not user:
            try:
                user = await create_user(
                    session=session,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    full_name=message.from_user.full_name,
                    referred_by=referred_by,
                )
                await notify_new_user(
                    bot=message.bot,
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    full_name=message.from_user.full_name,
                    referred_by=referred_by,
                )
            except Exception:
                user = await get_user(session, message.from_user.id)

            await message.answer(
                "👋 <b>Добро пожаловать в VEGA!</b>\n\n"
                "VEGA — пополняемая информационно-образовательная база. Сейчас доступны материалы "
                "о сне, питании, физической активности, восстановлении, работе мозга, добавках "
                "и мониторинге показателей.\n\n"
                "📈 VEGA развивается постепенно. В планах — психология, отношения и общение, "
                "мышление и развитие, обучение и навыки. Темы и порядок выхода могут меняться.\n\n"
                "<b>Публичный прайс:</b>\n"
                f"• полный доступ — <b>{PRODUCT_PRICE} ₽</b>;\n"
                "• оплата единоразовая, 100% предоплата;\n"
                f"• доступ — <b>{PRODUCT_ACCESS_TEXT}</b>;\n"
                "• подписки и повторных списаний нет.\n\n"
                "<b>Поставщик услуги:</b>\n"
                f"{escape(SELLER_FULL_NAME)}, самозанятый\n"
                f"Город: {escape(SELLER_CITY)}\n"
                f"ИНН: <code>{escape(SELLER_INN)}</code>\n"
                f"E-mail: <code>{escape(SELLER_EMAIL)}</code>\n"
                f"Лицензия / аккредитация: {escape(SELLER_LICENSE_INFO)}\n\n"
                "До оплаты можно посмотреть описание продукта, публичную оферту, политику обработки "
                "данных, сведения о поставщике и способы связи. Для продолжения ознакомься с офертой "
                "и подтверди согласие.",
                parse_mode="HTML",
                reply_markup=terms_keyboard(),
            )

        elif not user.agreed_to_terms:
            await message.answer(
                "📋 Для продолжения необходимо ознакомиться с публичной офертой и принять её условия.",
                reply_markup=terms_keyboard(),
            )

        elif not has_access(user):
            await message.answer(
                SUBSCRIPTION_REQUIRED_TEXT,
                parse_mode="HTML",
                reply_markup=pay_keyboard(),
            )

        else:
            await send_home(message, with_notice=True)


@router.callback_query(F.data == "terms:accept")
async def accept_terms(callback: CallbackQuery):
    async with async_session() as session:
        await agree_to_terms(session, callback.from_user.id)
        user = await get_user(session, callback.from_user.id)

        if has_access(user):
            await send_home(
                callback.message,
                with_notice=True,
                text="👋 Добро пожаловать! Выбери направление:",
            )
        else:
            await callback.message.edit_text(
                "✅ <b>Оферта принята.</b>\n\n" + SUBSCRIPTION_REQUIRED_TEXT,
                parse_mode="HTML",
                reply_markup=pay_keyboard(),
            )
    await callback.answer()


@router.callback_query(F.data == "terms:decline")
async def decline_terms(callback: CallbackQuery):
    await callback.message.edit_text(
        "😔 Без принятия публичной оферты оформить доступ невозможно.\n\n"
        "Если передумаешь — нажми /start"
    )
    await callback.answer()


@router.callback_query(F.data == "back:main")
async def back_to_main(callback: CallbackQuery):
    await edit_home(callback)
    await callback.answer()


@router.message(F.text.in_({"🏠 Главное меню", "🏠 Меню"}))
async def bottom_main_menu(message: Message):
    await send_home(message)


@router.message(F.text.in_({"🛠 Тех. поддержка", "🛠 Поддержка"}))
async def support(message: Message):
    await send_support_center(message)


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
