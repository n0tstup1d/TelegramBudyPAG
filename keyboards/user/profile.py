from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def profile_keyboard(referral_enabled: bool = False) -> InlineKeyboardMarkup:
    buttons = []

    if referral_enabled:
        buttons.append([
            InlineKeyboardButton(text="💸 Пригласить друга и заработать", callback_data="referral")
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Совместимость со старыми импортами:
# если где-то осталось `from keyboards.user.profile import withdraw_cancel_keyboard`,
# проект всё равно запустится.
def withdraw_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="withdraw:cancel")]
    ])
