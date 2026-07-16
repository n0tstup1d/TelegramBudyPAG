from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import (
    SUPPORT_URL,
    PARTNERSHIP_URL,
    PRODUCT_PRICE,
    PRODUCT_ACCESS_TEXT,
    OFFER_URL,
    PRIVACY_URL,
)


RELEASE_NOTICE = (
    "🏠 Главное меню\n"
    "Навигация и поддержка доступны на клавиатуре внизу."
)


SUBSCRIPTION_REQUIRED_TEXT = (
    "🔒 <b>Полный доступ к цифровому продукту VEGA</b>\n\n"
    "Сейчас в VEGA доступны материалы о сне, питании, физической активности, восстановлении, "
    "работе мозга, добавках и мониторинге показателей.\n\n"
    "📈 <b>VEGA развивается</b>\n"
    "База постепенно пополняется. В планах — психология, отношения и общение, "
    "мышление и развитие, обучение и навыки.\n\n"
    f"💳 Стоимость: <b>{PRODUCT_PRICE} ₽ единоразово</b>\n"
    "🔁 Подписки и повторных списаний нет\n"
    f"♾ Доступ: <b>{PRODUCT_ACCESS_TEXT}</b>\n"
    "⚡ После подтверждения оплаты доступ открывается автоматически.\n\n"
    "🛡 <b>Личное использование</b>\n"
    "Доступ предназначен для одного пользователя. Массовое копирование, публикация, передача "
    "и перепродажа материалов запрещены. Платные материалы защищены от штатной пересылки "
    "и содержат персональную лицензионную метку.\n\n"
    "До оплаты доступны описание продукта, документы, сведения о поставщике и поддержка."
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
    "<b>Планы развития:</b> психология, отношения и общение, мышление и развитие, обучение и навыки. "
    "Позже могут появиться направления о работе и карьере, цифровой среде, практической жизни, "
    "родительстве и развитии ребёнка. Темы, порядок выхода и состав будущих разделов могут меняться.\n\n"
    "Конкретный состав, доступный сейчас, показывается в разделах бота до оплаты.\n\n"
    f"Стоимость полного доступа: <b>{PRODUCT_PRICE} ₽ единоразово</b>.\n"
    f"Доступ: <b>{PRODUCT_ACCESS_TEXT}</b>.\n"
    "Подписки, автоматического продления и повторных списаний нет.\n\n"
    "<b>Правила доступа:</b> один пользователь, только личное использование. Передача аккаунта, "
    "массовое копирование, публикация и перепродажа материалов запрещены. Материалы могут "
    "содержать персональную лицензионную и техническую метку.\n\n"
    "Материалы носят общий информационно-образовательный характер и не заменяют персональную "
    "консультацию врача, психолога, педагога, юриста или другого профильного специалиста."
)

ROADMAP_TEXT = (
    "🗺 <b>Развитие VEGA</b>\n\n"
    "VEGA — пополняемая база знаний. Новые материалы и направления будут появляться постепенно, "
    "по мере подготовки и проверки.\n\n"
    "<b>Сначала планируем развивать:</b>\n"
    "• 🧠 психологию;\n"
    "• 💬 отношения и общение;\n"
    "• 🎯 мышление и развитие;\n"
    "• 📚 обучение и навыки.\n\n"
    "<b>В дальнейшем рассматриваем:</b>\n"
    "• 💼 работу, карьеру и финансовое поведение;\n"
    "• 📱 цифровую среду и технологии;\n"
    "• 🏠 практическую жизнь;\n"
    "• 👨‍👩‍👧 родительство и развитие ребёнка.\n\n"
    "Родительство и развитие ребёнка — большое самостоятельное направление. Оно будет формироваться "
    "поэтапно: возрастные ориентиры, обучение, речь, эмоции, поведение, границы и безопасность.\n\n"
    "Конкретные темы, состав разделов и порядок выхода могут меняться."
)


PAYMENT_PENDING_TEXT = (
    "⚙️ <b>Оплата временно недоступна</b>\n\n"
    "Платёжный модуль выключен администратором. Деньги не списываются. "
    "Попробуйте позже или обратитесь в поддержку.\n\n"
    "Описание продукта, публичная оферта, политика обработки персональных данных "
    "и сведения о поставщике доступны до оплаты."
)



def yookassa_checkout_keyboard(payment_url: str, payment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {PRODUCT_PRICE} ₽", url=payment_url)],
        [InlineKeyboardButton(text="✅ Я оплатил — проверить", callback_data=f"payment:check:{payment_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к условиям", callback_data="store:back")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support:start:tech")],
    ])

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


def documents_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_legal_button("📄 Публичная оферта", OFFER_URL, "legal:offer")],
        [_legal_button("🔐 Политика обработки данных", PRIVACY_URL, "legal:privacy")],
        [InlineKeyboardButton(text="🏷 Информация о поставщике", callback_data="store:seller")],
        [InlineKeyboardButton(text="💬 Написать в поддержку", callback_data="support:start:tech")],
        [InlineKeyboardButton(text="⬅️ К условиям покупки", callback_data="store:back")],
    ])


def terms_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Описание продукта", callback_data="store:product")],
        [InlineKeyboardButton(text="📄 Документы и поддержка", callback_data="store:documents")],
        [InlineKeyboardButton(text="✅ Принимаю оферту и правила", callback_data="terms:accept")],
        [InlineKeyboardButton(text="❌ Не принимаю", callback_data="terms:decline")],
    ])


def pay_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Купить доступ — {PRODUCT_PRICE} ₽", callback_data="store:checkout")],
        [InlineKeyboardButton(text="📦 Что входит в VEGA", callback_data="store:product")],
        [InlineKeyboardButton(text="📄 Документы и поддержка", callback_data="store:documents")],
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


def roadmap_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back:main")],
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
