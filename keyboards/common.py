from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import (
    SUPPORT_URL,
    PARTNERSHIP_URL,
    PRODUCT_PRICE,
    PRODUCT_ACCESS_YEARS,
    OFFER_URL,
    PRIVACY_URL,
)


RELEASE_NOTICE = (
    "⚠️ Проект запущен в режиме раннего доступа.\n"
    "Если что-то работает не так — нажми «🛠 Поддержка» снизу."
)


SUBSCRIPTION_REQUIRED_TEXT = (
    "🔒 <b>Полный доступ к цифровому продукту VEGA</b>\n\n"
    "Сейчас в VEGA доступны материалы о сне, питании, физической активности, восстановлении, "
    "работе мозга, добавках и мониторинге показателей.\n\n"
    "База может расширяться новыми направлениями — психологией, отношениями, воспитанием детей, "
    "обучением, продуктивностью и практическими инструментами для жизни. Будущие разделы не гарантируются "
    "до их фактического появления в боте.\n\n"
    f"💳 Стоимость: <b>{PRODUCT_PRICE} ₽ единоразово</b>\n"
    "🔁 Подписки и повторных списаний нет\n"
    f"🗓 Срок доступа: <b>{PRODUCT_ACCESS_YEARS} лет</b>\n"
    "⚡ После подтверждения оплаты доступ будет открываться автоматически.\n\n"
    "Сейчас магазин проходит активацию в Robokassa, поэтому реальная оплата временно недоступна. "
    "Описание продукта, оферта, политика обработки данных и реквизиты доступны ниже."
)

PRODUCT_CARD_TEXT = (
    "📦 <b>Цифровой продукт VEGA</b>\n\n"
    "VEGA — пополняемая база информационно-образовательных материалов.\n\n"
    "<b>На момент покупки доступны:</b>\n"
    "• сон и биоритмы;\n"
    "• питание и гидратация;\n"
    "• физическая активность и восстановление;\n"
    "• работа мозга, концентрация и внимание;\n"
    "• пищевые добавки и их ограничения;\n"
    "• анализы, носимые устройства и мониторинг показателей.\n\n"
    "В дальнейшем база может дополняться материалами о психологии, отношениях, воспитании детей, "
    "обучении, продуктивности, организации быта и другими практическими инструментами. "
    "Это направление развития проекта, а не обещание выпустить конкретный раздел или объём к определённой дате.\n\n"
    "Конкретный состав, доступный сейчас, показывается в разделах бота до оплаты.\n\n"
    f"Стоимость полного доступа: <b>{PRODUCT_PRICE} ₽ единоразово</b>.\n"
    f"Срок доступа: <b>{PRODUCT_ACCESS_YEARS} лет</b>.\n"
    "Подписки, автоматического продления и повторных списаний нет.\n\n"
    "Материалы носят общий информационно-образовательный характер и не заменяют персональную "
    "консультацию врача, психолога, педагога, юриста или другого профильного специалиста."
)

PAYMENT_PENDING_TEXT = (
    "🛠 <b>Подключение оплаты</b>\n\n"
    "Магазин VEGA сейчас проходит активацию в Robokassa. "
    "До завершения проверки списание денежных средств не производится.\n\n"
    f"После активации здесь появится защищённая платёжная страница на сумму <b>{PRODUCT_PRICE} ₽</b>, "
    "а доступ будет выдаваться автоматически после подтверждения платежа.\n\n"
    "Можно заранее ознакомиться с описанием продукта, публичной офертой, "
    "политикой обработки персональных данных и реквизитами продавца."
)


def _legal_button(text: str, url: str, callback_data: str) -> InlineKeyboardButton:
    if url:
        return InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def bottom_keyboard() -> ReplyKeyboardMarkup:
    """Постоянная нижняя клавиатура пользователя."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Меню")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🛠 Поддержка")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def terms_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Описание продукта", callback_data="store:product")],
        [_legal_button("📄 Публичная оферта", OFFER_URL, "legal:offer")],
        [_legal_button("🔐 Политика обработки данных", PRIVACY_URL, "legal:privacy")],
        [InlineKeyboardButton(text="📞 Реквизиты и поддержка", callback_data="store:seller")],
        [InlineKeyboardButton(text="✅ Принимаю оферту", callback_data="terms:accept")],
        [InlineKeyboardButton(text="❌ Не принимаю", callback_data="terms:decline")],
        [InlineKeyboardButton(text="💬 Связаться с нами", callback_data="support:start:tech")],
    ])


def pay_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Купить доступ — {PRODUCT_PRICE} ₽", callback_data="store:checkout")],
        [InlineKeyboardButton(text="📦 Что входит в VEGA", callback_data="store:product")],
        [_legal_button("📄 Публичная оферта", OFFER_URL, "legal:offer")],
        [_legal_button("🔐 Политика обработки данных", PRIVACY_URL, "legal:privacy")],
        [InlineKeyboardButton(text="📞 Реквизиты и поддержка", callback_data="store:seller")],
        [InlineKeyboardButton(text="💬 Написать в поддержку", callback_data="support:start:tech")],
    ])


def storefront_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Купить доступ — {PRODUCT_PRICE} ₽", callback_data="store:checkout")],
        [InlineKeyboardButton(text="⬅️ Назад к покупке", callback_data="store:back")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support:start:tech")],
    ])


def legal_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К условиям покупки", callback_data="store:back")],
        [InlineKeyboardButton(text="💬 Задать вопрос", callback_data="support:start:tech")],
    ])


def banned_keyboard() -> InlineKeyboardMarkup:
    if SUPPORT_URL:
        button = InlineKeyboardButton(text="💬 Обратиться в поддержку", url=SUPPORT_URL)
    else:
        button = InlineKeyboardButton(text="💬 Обратиться в поддержку", callback_data="support:start:tech")
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def support_keyboard() -> InlineKeyboardMarkup:
    """Внутренний центр обращений: пользователь пишет в бот, команда отвечает от лица проекта."""
    rows = [
        [InlineKeyboardButton(text="🛠 Написать в поддержку", callback_data="support:start:tech")],
        [InlineKeyboardButton(text="❓ Вопрос по контенту", callback_data="support:start:content")],
    ]
    if PARTNERSHIP_URL:
        rows.append([InlineKeyboardButton(text="🤝 Реклама и партнёрство", url=PARTNERSHIP_URL)])
    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Завершить обращение", callback_data="support:user_close")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="back:main")],
    ])
