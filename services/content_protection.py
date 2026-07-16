from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select

from config import (
    BOT_TOKEN,
    CONTENT_ALERT_COOLDOWN_SECONDS,
    CONTENT_HIDDEN_FINGERPRINT,
    CONTENT_LONG_BLOCK_SECONDS,
    CONTENT_LONG_MAX_VIEWS,
    CONTENT_LONG_WINDOW_SECONDS,
    CONTENT_MARK_SECRET,
    CONTENT_PROTECTION_ENABLED,
    CONTENT_SHORT_BLOCK_SECONDS,
    CONTENT_SHORT_MAX_VIEWS,
    CONTENT_SHORT_WINDOW_SECONDS,
    CONTENT_VISIBLE_WATERMARK,
    TEAM_CHAT_ID,
)
from database.engine import async_session
from database.models import ContentProtectionState, ContentStat, User

logger = logging.getLogger(__name__)

# Один процесс сериализует быстрые клики одного пользователя. Состояние блокировки
# хранится в PostgreSQL, поэтому перезапуск бота не снимает защитную паузу.
_user_locks: dict[int, asyncio.Lock] = {}


@dataclass(frozen=True)
class ContentGuardResult:
    allowed: bool
    license_code: str
    retry_after: int = 0
    reason: str | None = None


def _secret_bytes() -> bytes:
    # Отдельный CONTENT_MARK_SECRET предпочтительнее. BOT_TOKEN используется только
    # как безопасный fallback, чтобы обновление не отключило работающий бот.
    secret = CONTENT_MARK_SECRET or BOT_TOKEN
    return secret.encode("utf-8")


def _digest_for_user(user_id: int) -> bytes:
    return hmac.new(
        _secret_bytes(),
        f"vega-license:{user_id}".encode("utf-8"),
        hashlib.sha256,
    ).digest()


def make_license_code(user_id: int) -> str:
    """Стабильный необратимый код лицензии без публикации Telegram ID."""
    value = _digest_for_user(user_id).hex().upper()
    return f"{value[:4]}-{value[4:8]}-{value[8:12]}"


def make_hidden_fingerprint(user_id: int) -> str:
    """Невидимая метка для обнаружения источника скопированного текста.

    Telegram или сторонний редактор может удалить zero-width символы, поэтому это
    дополнительный слой, а не замена видимого кода лицензии.
    """
    if not CONTENT_HIDDEN_FINGERPRINT:
        return ""

    digest = _digest_for_user(user_id)[:6]
    bits = "".join(f"{byte:08b}" for byte in digest)
    zero = "\u2060"  # WORD JOINER
    one = "\u200b"   # ZERO WIDTH SPACE
    encoded = "".join(one if bit == "1" else zero for bit in bits)
    return f"\u2063{encoded}\u2063"


def protect_text(text: str, user_id: int) -> str:
    """Добавляет видимую и скрытую персональную метку к платному материалу."""
    value = str(text or "").strip()
    if not CONTENT_PROTECTION_ENABLED:
        return value

    code = make_license_code(user_id)
    hidden = make_hidden_fingerprint(user_id)

    if CONTENT_VISIBLE_WATERMARK:
        header = f"🔐 VEGA · лицензия {code}{hidden}"
        footer = "──────────\nТолько для личного использования. Передача и перепродажа запрещены."
        return f"{header}\n\n{value}\n\n{footer}"

    return f"{value}{hidden}"


def evaluate_content_limits(short_count: int, long_count: int) -> tuple[int, str | None]:
    """Возвращает длительность защитной паузы и её причину."""
    if long_count > CONTENT_LONG_MAX_VIEWS:
        return CONTENT_LONG_BLOCK_SECONDS, "слишком много материалов за длительный период"
    if short_count > CONTENT_SHORT_MAX_VIEWS:
        return CONTENT_SHORT_BLOCK_SECONDS, "слишком быстрое открытие материалов"
    return 0, None


def format_retry_after(seconds: int) -> str:
    seconds = max(1, int(seconds))
    if seconds < 60:
        return f"{seconds} сек."
    minutes = ceil(seconds / 60)
    if minutes < 60:
        return f"{minutes} мин."
    hours = ceil(minutes / 60)
    return f"{hours} ч."


def _lock_for(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


async def _notify_security_alert(
    bot,
    *,
    telegram_user,
    license_code: str,
    reason: str,
    short_count: int,
    long_count: int,
    blocked_until: datetime,
) -> None:
    if not TEAM_CHAT_ID:
        return

    username = f"@{telegram_user.username}" if getattr(telegram_user, "username", None) else "нет"
    full_name = getattr(telegram_user, "full_name", None) or "без имени"
    user_id = int(telegram_user.id)

    text = (
        "🛡 <b>VEGA: подозрительная активность</b>\n\n"
        f"Пользователь: {escape(full_name)} ({escape(username)})\n"
        f"Telegram ID: <code>{user_id}</code>\n"
        f"Код лицензии: <code>{license_code}</code>\n"
        f"Причина: {escape(reason)}\n"
        f"Открытий за {CONTENT_SHORT_WINDOW_SECONDS} сек.: <b>{short_count}</b>\n"
        f"Открытий за {CONTENT_LONG_WINDOW_SECONDS // 60} мин.: <b>{long_count}</b>\n"
        f"Защитная пауза до: <b>{blocked_until:%d.%m.%Y %H:%M:%S}</b>\n\n"
        "Постоянная блокировка автоматически не применяется. Проверьте пользователя вручную."
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Открыть пользователя", callback_data=f"admin:user_card:{user_id}")],
        [InlineKeyboardButton(text="🚫 Заблокировать доступ", callback_data=f"admin:ban:{user_id}")],
    ])

    try:
        await bot.send_message(TEAM_CHAT_ID, text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        logger.exception("Failed to send content protection alert for %s", user_id)


async def check_and_record_content_access(bot, telegram_user, content_id: str) -> ContentGuardResult:
    """Проверяет лимиты, записывает открытие и при необходимости ставит паузу."""
    user_id = int(telegram_user.id)
    license_code = make_license_code(user_id)

    if not CONTENT_PROTECTION_ENABLED:
        return ContentGuardResult(allowed=True, license_code=license_code)

    now = datetime.now()
    alert_payload: dict | None = None

    async with _lock_for(user_id):
        async with async_session() as session:
            user = await session.scalar(select(User).where(User.user_id == user_id))
            # Администраторы и модераторы могут быстро проверять контент без блокировки.
            if user and getattr(user, "role", None) in {"admin", "moderator"}:
                return ContentGuardResult(allowed=True, license_code=license_code)

            state = await session.scalar(
                select(ContentProtectionState)
                .where(ContentProtectionState.user_id == user_id)
                .with_for_update()
            )

            if state and state.blocked_until and state.blocked_until > now:
                retry_after = max(1, int((state.blocked_until - now).total_seconds()))
                return ContentGuardResult(
                    allowed=False,
                    license_code=license_code,
                    retry_after=retry_after,
                    reason=state.last_reason,
                )

            session.add(ContentStat(user_id=user_id, content_id=content_id[:128]))
            await session.flush()

            short_since = now - timedelta(seconds=CONTENT_SHORT_WINDOW_SECONDS)
            long_since = now - timedelta(seconds=CONTENT_LONG_WINDOW_SECONDS)

            short_count = int(await session.scalar(
                select(func.count(ContentStat.id)).where(
                    ContentStat.user_id == user_id,
                    ContentStat.clicked_at >= short_since,
                )
            ) or 0)
            long_count = int(await session.scalar(
                select(func.count(ContentStat.id)).where(
                    ContentStat.user_id == user_id,
                    ContentStat.clicked_at >= long_since,
                )
            ) or 0)

            block_seconds, reason = evaluate_content_limits(short_count, long_count)
            if not block_seconds or not reason:
                await session.commit()
                return ContentGuardResult(allowed=True, license_code=license_code)

            if state is None:
                state = ContentProtectionState(user_id=user_id)
                session.add(state)

            blocked_until = now + timedelta(seconds=block_seconds)
            state.blocked_until = blocked_until
            state.warning_count = int(state.warning_count or 0) + 1
            state.last_reason = reason
            state.updated_at = now

            should_alert = (
                state.last_alert_at is None
                or (now - state.last_alert_at).total_seconds() >= CONTENT_ALERT_COOLDOWN_SECONDS
            )
            if should_alert:
                state.last_alert_at = now
                alert_payload = {
                    "telegram_user": telegram_user,
                    "license_code": license_code,
                    "reason": reason,
                    "short_count": short_count,
                    "long_count": long_count,
                    "blocked_until": blocked_until,
                }

            await session.commit()

    if alert_payload:
        await _notify_security_alert(bot, **alert_payload)

    return ContentGuardResult(
        allowed=False,
        license_code=license_code,
        retry_after=block_seconds,
        reason=reason,
    )


async def clear_content_block(user_id: int) -> bool:
    async with async_session() as session:
        state = await session.scalar(
            select(ContentProtectionState).where(ContentProtectionState.user_id == user_id)
        )
        if state is None:
            return False
        state.blocked_until = None
        state.last_reason = None
        state.updated_at = datetime.now()
        await session.commit()
        return True
