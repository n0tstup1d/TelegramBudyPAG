from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TEAM_CHAT_ID, USERS_CHAT_ID


async def notify_new_user(bot: Bot, user_id: int, username: str, full_name: str, referred_by: int = None):
    username_text = f"@{username}" if username else "нет"
    ref_text = f"Реферал от: {referred_by}" if referred_by else "Органика"

    await bot.send_message(
        USERS_CHAT_ID,
        f"👤 Новый пользователь!\n\n"
        f"ID: {user_id}\n"
        f"Username: {username_text}\n"
        f"Имя: {full_name}\n"
        f"Источник: {ref_text}"
    )


async def notify_new_payment(bot: Bot, user_id: int, username: str, amount: int):
    username_text = f"@{username}" if username else str(user_id)

    await bot.send_message(
        TEAM_CHAT_ID,
        f"💳 Новая оплата!\n\n"
        f"👤 {username_text}\n"
        f"💰 Сумма: {amount} ₽"
    )


async def notify_withdrawal(bot: Bot, request_id: int, user_id: int, username: str, amount: int, requisites: str):
    username_text = f"@{username}" if username else str(user_id)

    await bot.send_message(
        TEAM_CHAT_ID,
        f"💸 Заявка на вывод #{request_id}\n\n"
        f"👤 {username_text} (id: {user_id})\n"
        f"💰 Сумма: {amount} ₽\n"
        f"💳 Реквизиты: {requisites}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✋ Взять в работу",
                callback_data=f"admin:take:{request_id}"
            )]
        ])
    )