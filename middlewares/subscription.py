from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from database.engine import async_session
from database.crud import get_user
from keyboards.common import pay_keyboard, banned_keyboard, SUBSCRIPTION_REQUIRED_TEXT


class SubscriptionMiddleware(BaseMiddleware):
    # разделы которые требуют подписки
    PROTECTED_CALLBACKS = (
        "section:", "topic:", "page:",
        "questions:", "question:", "sources:",
        "profile", "referral", "withdraw:"
    )

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # определяем user_id
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        async with async_session() as session:
            user = await get_user(session, user_id)

        # если юзера нет — пропускаем (start создаст его)
        if not user:
            return await handler(event, data)

        # проверяем бан
        if user.role == "banned":
            if isinstance(event, Message):
                await event.answer(
                    "🚫 Ваш аккаунт заблокирован.\n\n"
                    "Если считаете это ошибкой — обратитесь в поддержку.",
                    reply_markup=banned_keyboard()
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Ваш аккаунт заблокирован", show_alert=True)
            return

        # проверяем подписку только для защищённых разделов
        if isinstance(event, CallbackQuery):
            if any(event.data.startswith(cb) for cb in self.PROTECTED_CALLBACKS):
                if not user.has_subscription:
                    await event.answer(
                        "🔒 Для доступа необходима подписка",
                        show_alert=True
                    )
                    await event.message.answer(
                        SUBSCRIPTION_REQUIRED_TEXT,
                        reply_markup=pay_keyboard()
                    )
                    return

        return await handler(event, data)