from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from database.engine import async_session
from database.crud import get_user
from keyboards.common import pay_keyboard, banned_keyboard, SUBSCRIPTION_REQUIRED_TEXT
from services.access import has_access, forward_unpaid_message_to_support
from states.user import SupportStates


class SubscriptionMiddleware(BaseMiddleware):
    """Закрывает весь платный контент, включая нижнее меню и старые inline-кнопки."""

    FREE_CALLBACK_EXACT = {
        "noop",
        "support:user_close",
    }

    FREE_CALLBACK_PREFIXES = (
        "terms:",
        "store:",
        "legal:",
        "support:start:",
        "support_admin:",
    )

    FREE_MESSAGE_TEXTS = {
        "🛠 Поддержка",
        "🛠 Тех. поддержка",
    }

    LOCKED_MESSAGE_TEXTS = {
        "🏠 Меню",
        "🏠 Главное меню",
        "👤 Профиль",
    }

    FREE_COMMANDS = {
        "/start",
        "/product",
        "/buy",
        "/offer",
        "/privacy",
        "/seller",
    }

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.chat.type != "private":
                return await handler(event, data)
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            if event.message and event.message.chat.type != "private":
                return await handler(event, data)
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        async with async_session() as session:
            user = await get_user(session, user_id)

            if not user:
                return await handler(event, data)

            if getattr(user, "role", None) == "banned":
                if isinstance(event, Message):
                    await event.answer(
                        "🚫 Ваш аккаунт заблокирован.\n\n"
                        "Если считаете это ошибкой — обратитесь в поддержку.",
                        reply_markup=banned_keyboard(),
                    )
                else:
                    await event.answer("🚫 Ваш аккаунт заблокирован", show_alert=True)
                return

            if has_access(user):
                return await handler(event, data)

            # Если пользователь уже начал диалог поддержки — пропускаем в handlers/user/support.py.
            state = data.get("state")
            if isinstance(event, Message) and state:
                current_state = await state.get_state()
                if current_state == SupportStates.waiting_message.state:
                    return await handler(event, data)

            if isinstance(event, CallbackQuery):
                callback_data = event.data or ""
                is_free_callback = (
                    callback_data in self.FREE_CALLBACK_EXACT
                    or any(callback_data.startswith(prefix) for prefix in self.FREE_CALLBACK_PREFIXES)
                )

                if is_free_callback:
                    return await handler(event, data)

                await event.answer("🔒 Доступ открыт только участникам проекта", show_alert=True)

                if event.message:
                    await event.message.answer(
                        SUBSCRIPTION_REQUIRED_TEXT,
                        parse_mode="HTML",
                        reply_markup=pay_keyboard(),
                    )
                return

            if isinstance(event, Message):
                text = event.text or ""

                command = text.split(maxsplit=1)[0].lower() if text.startswith("/") else ""
                command = command.split("@", 1)[0]
                if command in self.FREE_COMMANDS:
                    return await handler(event, data)

                if text in self.FREE_MESSAGE_TEXTS:
                    return await handler(event, data)

                if text in self.LOCKED_MESSAGE_TEXTS or text.startswith("/"):
                    await event.answer(
                        SUBSCRIPTION_REQUIRED_TEXT,
                        parse_mode="HTML",
                        reply_markup=pay_keyboard(),
                    )
                    return

                await forward_unpaid_message_to_support(event, session, user=user)
                return

        return await handler(event, data)
