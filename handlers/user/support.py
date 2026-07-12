from datetime import datetime
from html import escape
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import SUPPORT_DIALOG_CHAT_ID
from database.crud import get_user
from database.engine import async_session
from database.models import SupportTicket, SupportMessageLink
from keyboards.common import support_cancel_keyboard, bottom_keyboard, support_keyboard
from services.navigation import get_main_menu_markup, SUPPORT_CENTER_TEXT
from states.user import SupportStates

router = Router()
logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "tech": "🛠 Техподдержка",
    "content": "❓ Вопрос по контенту",
    "support": "🛠 Поддержка",
}

NAV_TEXTS = {"🏠 Меню", "🏠 Главное меню", "👤 Профиль", "🛠 Поддержка", "🛠 Тех. поддержка"}


async def is_staff_user(user_id: int) -> bool:
    async with async_session() as session:
        user = await get_user(session, user_id)
        return bool(user and user.role in ("admin", "moderator"))


def format_exception(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    return text[:1500]


async def build_support_diagnostics(bot) -> str:
    """Проверяет, может ли бот работать с форум-группой поддержки."""
    lines: list[str] = []
    chat_id = SUPPORT_DIALOG_CHAT_ID

    lines.append("🧪 Проверка поддержки")
    lines.append("")
    lines.append(f"SUPPORT_DIALOG_CHAT_ID: <code>{chat_id}</code>")

    chat = None
    try:
        chat = await bot.get_chat(chat_id)
        lines.append(f"Чат найден: <b>{escape(chat.title or str(chat.id))}</b>")
        lines.append(f"Тип чата: <code>{escape(str(chat.type))}</code>")
        lines.append(f"Темы включены: <code>{escape(str(getattr(chat, 'is_forum', None)))}</code>")
    except Exception as exc:
        lines.append("❌ Бот не может получить чат.")
        lines.append(f"Ошибка: <code>{escape(format_exception(exc))}</code>")
        lines.append("")
        lines.append("Проверь, что ID указан с <code>-100</code>, бот добавлен в группу и проект перезапущен после изменения .env.")
        return "\n".join(lines)

    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
        lines.append("")
        lines.append(f"Статус бота в группе: <code>{escape(str(getattr(member, 'status', None)))}</code>")
        lines.append(f"can_manage_topics: <code>{escape(str(getattr(member, 'can_manage_topics', None)))}</code>")
        lines.append(f"can_delete_messages: <code>{escape(str(getattr(member, 'can_delete_messages', None)))}</code>")
        lines.append(f"can_pin_messages: <code>{escape(str(getattr(member, 'can_pin_messages', None)))}</code>")
    except Exception as exc:
        lines.append("")
        lines.append("⚠️ Не удалось проверить права бота.")
        lines.append(f"Ошибка: <code>{escape(format_exception(exc))}</code>")

    if not getattr(chat, "is_forum", False):
        lines.append("")
        lines.append("❌ Это не forum-группа или в группе не включены темы.")
        lines.append("Включи темы в настройках группы: <b>Group Settings → Topics</b>.")
        return "\n".join(lines)

    lines.append("")
    try:
        topic = await bot.create_forum_topic(
            chat_id=chat_id,
            name="🧪 Проверка поддержки",
        )
        lines.append(f"✅ Тестовая тема создана. thread_id: <code>{topic.message_thread_id}</code>")
        try:
            await bot.send_message(
                chat_id,
                "✅ Бот может писать в темы поддержки.",
                message_thread_id=topic.message_thread_id,
            )
            lines.append("✅ Бот может отправлять сообщения в тему.")
        except Exception as exc:
            lines.append("❌ Тема создана, но бот не смог написать в неё.")
            lines.append(f"Ошибка: <code>{escape(format_exception(exc))}</code>")
        try:
            await bot.delete_forum_topic(chat_id=chat_id, message_thread_id=topic.message_thread_id)
            lines.append("✅ Тестовая тема удалена.")
        except Exception as exc:
            lines.append("⚠️ Тестовая тема создана, но не удалена автоматически. Можно удалить вручную.")
            lines.append(f"Ошибка удаления: <code>{escape(format_exception(exc))}</code>")
    except Exception as exc:
        lines.append("❌ Бот не смог создать тему.")
        lines.append(f"Ошибка: <code>{escape(format_exception(exc))}</code>")
        lines.append("")
        lines.append("Чаще всего причина одна из этих:")
        lines.append("1. Бот не админ в этой группе.")
        lines.append("2. У бота не включено право <b>Управление темами / Manage Topics</b>.")
        lines.append("3. В группе не включены темы.")
        lines.append("4. В .env указан не тот ID группы или бот не был перезапущен.")

    return "\n".join(lines)


@router.message(Command("support_check"))
async def support_check(message: Message):
    if not await is_staff_user(message.from_user.id):
        return
    text = await build_support_diagnostics(message.bot)
    await message.answer(text, parse_mode="HTML")


def staff_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Закрыть обращение", callback_data=f"support_admin:close:{ticket_id}")]
    ])


def user_reply_keyboard(category: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Ответить", callback_data=f"support:start:{category}")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="back:main")],
    ])


def user_display_name(user) -> str:
    username = f"@{user.username}" if user and user.username else "без username"
    full_name = user.full_name if user and user.full_name else "без имени"
    return f"{escape(full_name)} ({escape(username)})"


def make_topic_name(ticket_id: int, user, category: str) -> str:
    label = "Контент" if category == "content" else "Поддержка"
    full_name = user.full_name if user and user.full_name else "Пользователь"
    username = f"@{user.username}" if user and user.username else str(user.user_id if user else "")
    raw = f"#{ticket_id} • {full_name} • {label} • {username}"
    return raw[:120]


def ticket_header(ticket: SupportTicket, user, label: str) -> str:
    return (
        f"📩 Обращение #{ticket.id} • {label}\n"
        f"👤 {user_display_name(user)}\n"
        f"ID: <code>{ticket.user_id}</code>\n\n"
        "Это отдельная тема клиента. Пиши ответ прямо в эту тему — "
        "пользователь получит его в личный чат с ботом от лица проекта."
    )


async def get_or_create_ticket(session, user_id: int, category: str) -> SupportTicket:
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
        staff_chat_id=SUPPORT_DIALOG_CHAT_ID,
        last_message_at=datetime.now(),
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def ensure_ticket_topic(bot, session, ticket: SupportTicket, user) -> SupportTicket:
    """Создаёт отдельную тему в рабочей группе для обращения, если её ещё нет."""
    if ticket.staff_thread_id:
        return ticket

    topic_name = make_topic_name(ticket.id, user, ticket.category)
    topic = await bot.create_forum_topic(
        chat_id=SUPPORT_DIALOG_CHAT_ID,
        name=topic_name,
    )

    ticket.staff_chat_id = SUPPORT_DIALOG_CHAT_ID
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
        staff_chat_id=SUPPORT_DIALOG_CHAT_ID,
        staff_message_id=staff_message_id,
        user_message_id=user_message_id,
        direction=direction,
    ))
    await session.commit()


@router.callback_query(F.data.startswith("support:start:"))
async def start_support_dialog(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    category = callback.data.split(":", 2)[2]
    label = CATEGORY_LABELS.get(category, CATEGORY_LABELS["support"])

    await state.set_state(SupportStates.waiting_message)
    await state.update_data(category=category)

    await callback.message.edit_text(
        f"{label}\n\n"
        "Напиши сообщение сюда, в чат с ботом.\n",
        reply_markup=support_cancel_keyboard(),
    )


@router.callback_query(F.data == "support:user_close")
async def close_user_support_dialog(callback: CallbackQuery, state: FSMContext):
    await callback.answer("Обращение закрыто")
    await state.clear()
    await callback.message.edit_text(
        "✅ Обращение закрыто.\n\n"
        "Если понадобится помощь — снова нажми «🛠 Поддержка» снизу.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back:main")]
        ]),
    )


@router.message(SupportStates.waiting_message)
async def receive_user_support_message(message: Message, state: FSMContext):
    if message.text in NAV_TEXTS:
        await state.clear()
        if message.text in {"🏠 Меню", "🏠 Главное меню"}:
            await message.answer("👋 Выбери направление:", reply_markup=await get_main_menu_markup())
        elif message.text in {"🛠 Поддержка", "🛠 Тех. поддержка"}:
            await message.answer(SUPPORT_CENTER_TEXT, reply_markup=support_keyboard())
        else:
            await message.answer("Диалог с поддержкой закрыт. Нажми кнопку ещё раз.", reply_markup=bottom_keyboard())
        return

    data = await state.get_data()
    category = data.get("category", "support")
    label = CATEGORY_LABELS.get(category, CATEGORY_LABELS["support"])

    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        ticket = await get_or_create_ticket(session, message.from_user.id, category)

        try:
            ticket = await ensure_ticket_topic(message.bot, session, ticket, user)
        except Exception as exc:
            logger.exception("Failed to create support forum topic")
            detail = format_exception(exc)
            await message.answer(
                "⚠️ Не удалось создать внутренний чат обращения.\n\n"
                "Я уже передал техническую ошибку команде, если рабочая группа доступна. "
                "Администратору нужно выполнить команду /support_check и проверить права бота."
            )
            # Админам всё равно отправляем ошибку в общий чат, если возможно.
            try:
                await message.bot.send_message(
                    SUPPORT_DIALOG_CHAT_ID,
                    "⚠️ Ошибка создания темы поддержки\n\n"
                    f"Пользователь: <code>{message.from_user.id}</code>\n"
                    f"Категория: <code>{escape(category)}</code>\n"
                    f"Ошибка: <code>{escape(detail)}</code>\n\n"
                    "Проверьте /support_check",
                    parse_mode="HTML",
                )
            except Exception:
                logger.exception("Failed to send support topic error to staff chat")
            return

        header = ticket_header(ticket, user, label)
        thread_id = ticket.staff_thread_id

        if message.text:
            sent = await message.bot.send_message(
                SUPPORT_DIALOG_CHAT_ID,
                f"{header}\n\n<b>Сообщение пользователя:</b>\n{escape(message.text)}",
                message_thread_id=thread_id,
                parse_mode="HTML",
                reply_markup=staff_ticket_keyboard(ticket.id),
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
                SUPPORT_DIALOG_CHAT_ID,
                f"{header}\n\n<b>Сообщение пользователя:</b>",
                message_thread_id=thread_id,
                parse_mode="HTML",
                reply_markup=staff_ticket_keyboard(ticket.id),
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
                chat_id=SUPPORT_DIALOG_CHAT_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=thread_id,
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
        "✅ Сообщение отправлено команде.\n\n"
        "Можешь отправить ещё одно сообщение или завершить обращение.",
        reply_markup=support_cancel_keyboard(),
    )


async def find_ticket_for_staff_message(session, message: Message) -> SupportTicket | None:
    """Ищет обращение по теме форума или по reply на сообщение бота."""
    thread_id = getattr(message, "message_thread_id", None)
    if thread_id:
        result = await session.execute(
            select(SupportTicket)
            .where(
                SupportTicket.staff_chat_id == message.chat.id,
                SupportTicket.staff_thread_id == thread_id,
                SupportTicket.status == "open",
            )
            .order_by(SupportTicket.id.desc())
        )
        ticket = result.scalar_one_or_none()
        if ticket:
            return ticket

    if message.reply_to_message:
        result = await session.execute(
            select(SupportMessageLink)
            .where(
                SupportMessageLink.staff_chat_id == message.chat.id,
                SupportMessageLink.staff_message_id == message.reply_to_message.message_id,
            )
            .order_by(SupportMessageLink.id.desc())
        )
        link = result.scalar_one_or_none()
        if link:
            return await session.get(SupportTicket, link.ticket_id)

    return None


@router.message(F.chat.id == SUPPORT_DIALOG_CHAT_ID)
async def receive_staff_topic_message(message: Message):
    """Любое сообщение сотрудника в теме обращения отправляется пользователю."""
    if message.from_user and message.from_user.is_bot:
        return

    if message.text and message.text.startswith("/"):
        return

    async with async_session() as session:
        ticket = await find_ticket_for_staff_message(session, message)
        if not ticket:
            return

        if ticket.status == "closed":
            await message.reply("Это обращение уже закрыто. Ответ пользователю не отправлен.")
            return

        try:
            if message.text:
                sent = await message.bot.send_message(
                    ticket.user_id,
                    f"💬 Ответ команды:\n\n{message.text}",
                    reply_markup=user_reply_keyboard(ticket.category),
                )
                user_message_id = sent.message_id
            else:
                header = await message.bot.send_message(
                    ticket.user_id,
                    "💬 Ответ команды:",
                    reply_markup=user_reply_keyboard(ticket.category),
                )
                copied = await message.bot.copy_message(
                    chat_id=ticket.user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                user_message_id = copied.message_id or header.message_id
        except Exception as exc:
            await message.reply(f"⚠️ Не удалось отправить ответ пользователю: {exc}")
            return

        ticket.last_message_at = datetime.now()
        session.add(SupportMessageLink(
            ticket_id=ticket.id,
            user_id=ticket.user_id,
            staff_chat_id=message.chat.id,
            staff_message_id=message.message_id,
            user_message_id=user_message_id,
            direction="staff_to_user",
        ))
        await session.commit()

    await message.reply("✅ Ответ отправлен пользователю")


@router.callback_query(F.data.startswith("support_admin:close:"))
async def close_ticket_from_staff(callback: CallbackQuery):
    if callback.message.chat.id != SUPPORT_DIALOG_CHAT_ID:
        await callback.answer("Недоступно", show_alert=True)
        return

    await callback.answer()
    ticket_id = int(callback.data.split(":")[2])

    async with async_session() as session:
        ticket = await session.get(SupportTicket, ticket_id)
        if not ticket:
            await callback.answer("Обращение не найдено", show_alert=True)
            return

        if ticket.status != "closed":
            ticket.status = "closed"
            ticket.closed_at = datetime.now()
            await session.commit()
            try:
                await callback.bot.send_message(
                    ticket.user_id,
                    "✅ Обращение закрыто командой.\n\n"
                    "Если вопрос остался — создай новое обращение через «🛠 Поддержка».",
                    reply_markup=user_reply_keyboard(ticket.category),
                )
            except Exception:
                pass

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    try:
        await callback.message.answer(
            f"✅ Обращение #{ticket_id} закрыто.",
            message_thread_id=getattr(callback.message, "message_thread_id", None),
        )
    except Exception:
        pass
