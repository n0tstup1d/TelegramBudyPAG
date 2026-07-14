from __future__ import annotations

from datetime import datetime
from html import escape
import logging

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from config import SUPPORT_DIALOG_CHAT_ID, TEAM_CHAT_ID
from database.crud import get_user
from database.models import SupportTicket, SupportMessageLink
from keyboards.common import SUBSCRIPTION_REQUIRED_TEXT
from services.access_policy import has_access
from services.support_policy import STAFF_CONTENT_WARNING, validate_support_message

logger = logging.getLogger(__name__)

def support_chat_id() -> int | None:
    return SUPPORT_DIALOG_CHAT_ID or TEAM_CHAT_ID


def staff_ticket_keyboard(ticket_id: int, category: str = "tech") -> InlineKeyboardMarkup:
    rows = []
    if category == "content":
        rows.append([
            InlineKeyboardButton(
                text="🧭 Отправить безопасный шаблон",
                callback_data=f"support_admin:safe_reply:{ticket_id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="✅ Закрыть обращение", callback_data=f"support_admin:close:{ticket_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_display_name(user, telegram_user=None) -> str:
    if user:
        full_name = user.full_name or "без имени"
        username = f"@{user.username}" if user.username else "без username"
    else:
        full_name = getattr(telegram_user, "full_name", None) or "без имени"
        username = f"@{telegram_user.username}" if telegram_user and telegram_user.username else "без username"

    return f"{escape(full_name)} ({escape(username)})"


def make_topic_name(ticket_id: int, user, telegram_user, category: str) -> str:
    label = "Контент" if category == "content" else "Поддержка"
    full_name = getattr(user, "full_name", None) or getattr(telegram_user, "full_name", None) or "Пользователь"

    if getattr(user, "username", None):
        username = f"@{user.username}"
    elif telegram_user and telegram_user.username:
        username = f"@{telegram_user.username}"
    else:
        username = str(getattr(user, "user_id", None) or getattr(telegram_user, "id", ""))

    return f"#{ticket_id} • {full_name} • {label} • {username}"[:120]


def ticket_header(ticket: SupportTicket, user, telegram_user, label: str) -> str:
    text = (
        f"📩 Обращение #{ticket.id} • {label}\n"
        f"👤 {user_display_name(user, telegram_user)}\n"
        f"ID: <code>{ticket.user_id}</code>\n\n"
        "Пользователь пока без доступа. Ответьте прямо в эту тему или reply на сообщение — "
        "бот отправит ответ пользователю в личный чат."
    )
    if ticket.category == "content":
        text += f"\n\n{STAFF_CONTENT_WARNING}"
    return text


async def get_or_create_ticket(session, user_id: int, category: str = "tech") -> SupportTicket:
    result = await session.execute(
        select(SupportTicket)
        .where(
            SupportTicket.user_id == user_id,
            SupportTicket.category == category,
            SupportTicket.status == "open",
        )
        .order_by(SupportTicket.id.desc())
    )
    ticket = result.scalar_one_or_none()

    if ticket:
        ticket.last_message_at = datetime.now()
        await session.commit()
        await session.refresh(ticket)
        return ticket

    ticket = SupportTicket(
        user_id=user_id,
        category=category,
        status="open",
        staff_chat_id=support_chat_id(),
        last_message_at=datetime.now(),
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def ensure_ticket_topic(bot, session, ticket: SupportTicket, user, telegram_user) -> SupportTicket:
    """Создаёт отдельную тему в support-группе. Если не получится — вызывающий код сделает fallback."""
    if ticket.staff_thread_id:
        return ticket

    chat_id = support_chat_id()
    topic_name = make_topic_name(ticket.id, user, telegram_user, ticket.category)

    topic = await bot.create_forum_topic(chat_id=chat_id, name=topic_name)

    ticket.staff_chat_id = chat_id
    ticket.staff_thread_id = topic.message_thread_id
    ticket.staff_topic_name = topic_name
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def save_staff_message_link(
    session,
    ticket_id: int,
    user_id: int,
    staff_message_id: int,
    user_message_id: int | None,
    direction: str,
) -> None:
    session.add(SupportMessageLink(
        ticket_id=ticket_id,
        user_id=user_id,
        staff_chat_id=support_chat_id(),
        staff_message_id=staff_message_id,
        user_message_id=user_message_id,
        direction=direction,
    ))
    await session.commit()


def _message_thread_kwargs(thread_id: int | None) -> dict:
    if thread_id:
        return {"message_thread_id": thread_id}
    return {}


async def forward_unpaid_message_to_support(message: Message, session, user=None, category: str = "tech") -> bool:
    """Создаёт обращение и отправляет любое сообщение пользователя без доступа в группу поддержки."""
    chat_id = support_chat_id()

    if not chat_id:
        await message.answer("⚠️ Поддержка временно не настроена. Команде нужно проверить SUPPORT_DIALOG_CHAT_ID.")
        return False

    valid, error_text = validate_support_message(message, category)
    if not valid:
        await message.answer(f"⚠️ {error_text}")
        return False

    if not user:
        user = await get_user(session, message.from_user.id)

    ticket = await get_or_create_ticket(session, message.from_user.id, category)
    label = CATEGORY_LABELS.get(category, CATEGORY_LABELS["support"])

    thread_id = ticket.staff_thread_id
    topic_error = None

    if not thread_id:
        try:
            ticket = await ensure_ticket_topic(message.bot, session, ticket, user, message.from_user)
            thread_id = ticket.staff_thread_id
        except Exception as exc:
            topic_error = str(exc) or exc.__class__.__name__
            logger.exception("Failed to create support topic for unpaid user")

    header = ticket_header(ticket, user, message.from_user, label)

    if topic_error:
        header += (
            "\n\n⚠️ Не удалось создать отдельную тему поддержки. "
            "Сообщение отправлено в общий чат. Для ответа пользователю нажмите reply на сообщение."
            f"\nОшибка: <code>{escape(topic_error[:500])}</code>"
        )

    send_kwargs = _message_thread_kwargs(thread_id)

    if message.text:
        sent = await message.bot.send_message(
            chat_id,
            f"{header}\n\n<b>Сообщение пользователя:</b>\n{escape(message.text)}",
            parse_mode="HTML",
            reply_markup=staff_ticket_keyboard(ticket.id, ticket.category),
            **send_kwargs,
        )

        await save_staff_message_link(
            session=session,
            ticket_id=ticket.id,
            user_id=message.from_user.id,
            staff_message_id=sent.message_id,
            user_message_id=message.message_id,
            direction="user_to_staff",
        )
    else:
        header_message = await message.bot.send_message(
            chat_id,
            f"{header}\n\n<b>Сообщение пользователя:</b>",
            parse_mode="HTML",
            reply_markup=staff_ticket_keyboard(ticket.id, ticket.category),
            **send_kwargs,
        )

        await save_staff_message_link(
            session=session,
            ticket_id=ticket.id,
            user_id=message.from_user.id,
            staff_message_id=header_message.message_id,
            user_message_id=message.message_id,
            direction="user_to_staff",
        )

        copied = await message.bot.copy_message(
            chat_id=chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            **send_kwargs,
        )

        await save_staff_message_link(
            session=session,
            ticket_id=ticket.id,
            user_id=message.from_user.id,
            staff_message_id=copied.message_id,
            user_message_id=message.message_id,
            direction="user_to_staff",
        )

    await message.answer(
        "✅ Сообщение передано команде.\n\n"
        "Сейчас доступ к материалам закрыт. Если тебя пригласили — команда увидит сообщение и сможет выдать доступ."
    )
    return True
