from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import SUPPORT_URL, PARTNERSHIP_URL, CONTENT_URL


TEST_NOTICE = (
    "⚠️ Бот работает в режиме закрытого тестирования.\n"
    "Если что-то работает не так — нажми «🛠 Поддержка» снизу."
)


SUBSCRIPTION_REQUIRED_TEXT = (
    "🔒 Доступ к материалам открыт только участникам закрытого тестирования.\n\n"
    "Чтобы попасть внутрь, нужно принять соглашение и получить подписку. "
    "На время теста доступ выдаётся администратором вручную."
)


def bottom_keyboard() -> ReplyKeyboardMarkup:
    """Постоянная нижняя клавиатура пользователя.

    Основной экран не перегружаем служебными кнопками: контент остаётся в inline-меню,
    а навигация/профиль/помощь всегда доступны под полем ввода.
    """
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
        [InlineKeyboardButton(text="📋 Читать соглашение", url="https://telegra.ph/твоя-ссылка")],
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="terms:accept")],
        [InlineKeyboardButton(text="❌ Не принимаю", callback_data="terms:decline")],
        [InlineKeyboardButton(text="💬 Связаться с нами", url=SUPPORT_URL)],
    ])


def pay_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data="pay")],
        [InlineKeyboardButton(text="💬 Получить доступ / поддержка", url=SUPPORT_URL)],
    ])


def banned_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Обратиться в поддержку", url=SUPPORT_URL)]
    ])


def support_keyboard() -> InlineKeyboardMarkup:
    """Внутренний центр обращений: пользователь пишет в бот, команда отвечает от лица проекта."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Написать в поддержку", callback_data="support:start:tech")],
        [InlineKeyboardButton(text="❓ Вопрос по контенту", callback_data="support:start:content")],
        [InlineKeyboardButton(text="🤝 Реклама и партнёрство", url=PARTNERSHIP_URL)],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="back:main")],
    ])


def support_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Завершить обращение", callback_data="support:user_close")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="back:main")],
    ])
