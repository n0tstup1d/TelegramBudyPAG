from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from time import monotonic
from typing import Any, Awaitable, Callable, Deque, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from config import RATE_LIMIT_BLOCK_SECONDS, RATE_LIMIT_MAX_ACTIONS, RATE_LIMIT_WINDOW_SECONDS


class RateLimitMiddleware(BaseMiddleware):
    """Простой локальный антиспам для личного чата.

    Ограничитель не применяется к рабочим группам. При нескольких экземплярах бота
    лимит действует отдельно на каждом процессе; для распределённого лимита нужен Redis.
    """

    def __init__(
        self,
        max_actions: int = RATE_LIMIT_MAX_ACTIONS,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
        block_seconds: int = RATE_LIMIT_BLOCK_SECONDS,
    ) -> None:
        self.max_actions = max(1, max_actions)
        self.window_seconds = max(1, window_seconds)
        self.block_seconds = max(1, block_seconds)
        self._events: Dict[int, Deque[float]] = defaultdict(deque)
        self._blocked_until: Dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def _allowed(self, user_id: int) -> tuple[bool, int]:
        now = monotonic()
        async with self._lock:
            blocked_until = self._blocked_until.get(user_id, 0.0)
            if blocked_until > now:
                return False, max(1, int(blocked_until - now))

            events = self._events[user_id]
            cutoff = now - self.window_seconds
            while events and events[0] < cutoff:
                events.popleft()

            if len(events) >= self.max_actions:
                self._blocked_until[user_id] = now + self.block_seconds
                events.clear()
                return False, self.block_seconds

            events.append(now)
            return True, 0

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        chat = getattr(event, "chat", None)
        if isinstance(event, CallbackQuery):
            chat = getattr(event.message, "chat", None)

        if chat is not None and getattr(chat, "type", None) != "private":
            return await handler(event, data)

        user = getattr(event, "from_user", None)
        if user is None or getattr(user, "is_bot", False):
            return await handler(event, data)

        allowed, retry_after = await self._allowed(user.id)
        if allowed:
            return await handler(event, data)

        text = f"Слишком много действий. Попробуй снова через {retry_after} сек."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(f"⏳ {text}")
        return None
