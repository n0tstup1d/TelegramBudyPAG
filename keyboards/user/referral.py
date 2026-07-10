from urllib.parse import quote

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def make_share_url(ref_link: str, reward: int | None = None) -> str:
    reward_text = f" За регистрацию по ссылке мне начислят {reward} ₽." if reward else ""
    text = (
        "Привет! Я нашёл полезный бот по биохакингу: сон, питание, добавки и восстановление."
        f"{reward_text} Заходи по моей ссылке 👇"
    )
    return (
        "https://t.me/share/url"
        f"?url={quote(ref_link, safe='')}"
        f"&text={quote(text, safe='')}"
    )


def referral_keyboard(
    balance: int,
    min_withdrawal: int,
    referral_enabled: bool = True,
    ref_link: str | None = None,
    reward: int | None = None,
) -> InlineKeyboardMarkup:
    buttons = []

    if referral_enabled and ref_link:
        buttons.append([
            InlineKeyboardButton(
                text=f"📤 Пригласить друга (+{reward} ₽)" if reward else "📤 Пригласить друга",
                url=make_share_url(ref_link, reward)
            )
        ])

    if referral_enabled:
        # Кнопка всегда называется просто "Вывод".
        # Если баланса не хватает, handler покажет alert по центру экрана.
        buttons.append([
            InlineKeyboardButton(text="💸 Вывод", callback_data="withdraw:start")
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def withdraw_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="withdraw:cancel")]
    ])


def after_withdraw_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤝 К реферальной системе", callback_data="referral")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="back:main")],
    ])
