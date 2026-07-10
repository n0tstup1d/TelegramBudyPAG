from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import SUPPORT_URL, PARTNERSHIP_URL, CONTENT_URL


TEST_NOTICE = (
    "⚠️ Бот работает в тестовом режиме.\n"
    "Если что-то работает не так — нажми «🛠 Тех. поддержка» снизу."
)


def bottom_keyboard() -> ReplyKeyboardMarkup:
    """Постоянная нижняя клавиатура пользователя.

    Основной экран не перегружаем служебными кнопками: контент остаётся в inline-меню,
    а навигация/профиль/помощь всегда доступны под полем ввода.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главное меню")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🛠 Тех. поддержка")],
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
        [InlineKeyboardButton(text="💬 Проблемы с оплатой?", url=SUPPORT_URL)],
    ])


def banned_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Обратиться в поддержку", url=SUPPORT_URL)]
    ])


def support_keyboard() -> InlineKeyboardMarkup:
    """Контакты спрятаны за одним осознанным действием — без перегруза главного меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Тех. поддержка", url=SUPPORT_URL)],
        [InlineKeyboardButton(text="❓ Вопрос по контенту", url=CONTENT_URL)],
        [InlineKeyboardButton(text="🤝 Реклама и сотрудничество", url=PARTNERSHIP_URL)],
    ])
