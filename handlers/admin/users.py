from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func

from database.engine import async_session
from database.models import ContentProtectionState, ContentStat, User
from database.crud import get_user
from services.content_protection import clear_content_block, make_license_code
from handlers.admin.guards import is_admin, is_superadmin
from states.admin import AdminUserStates
from keyboards.admin.users import users_menu, users_list_menu, user_card_menu, role_menu, find_user_menu

router = Router()


@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "👤 Управление пользователями",
        reply_markup=users_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:user_find")
async def admin_user_find(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(AdminUserStates.waiting_user_id)
    await state.update_data(mode="find")
    await callback.message.edit_text(
        "🔍 Введи username (@username) или Telegram ID:",
        reply_markup=find_user_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:role_find")
async def admin_role_find(callback: CallbackQuery, state: FSMContext):
    if not await is_superadmin(callback.from_user.id):
        await callback.answer("Только главный админ может менять роли", show_alert=True)
        return

    await state.set_state(AdminUserStates.waiting_user_id)
    await state.update_data(mode="role_change")
    await callback.message.edit_text(
        "🎭 Назначить роль\n\n"
        "Введи username (@username) или Telegram ID пользователя:",
        reply_markup=find_user_menu()
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_user_id)
async def admin_user_search(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    state_data = await state.get_data()
    mode = state_data.get("mode", "find")
    search = message.text.strip().lstrip("@")

    async with async_session() as session:
        if search.isdigit():
            result = await session.execute(
                select(User).where(User.user_id == int(search))
            )
        else:
            result = await session.execute(
                select(User).where(User.username == search)
            )
        user = result.scalar_one_or_none()

    await state.clear()

    if not user:
        await message.answer(
            "❌ Пользователь не найден",
            reply_markup=find_user_menu()
        )
        return

    if mode == "role_change":
        role_text = {
            "user": "👤 Пользователь",
            "moderator": "🛡 Модератор",
            "admin": "⚙️ Администратор",
            "banned": "🚫 Заблокирован",
        }.get(user.role, user.role)
        username = f"@{user.username}" if user.username else "нет"
        await message.answer(
            f"🎭 Назначить роль\n\n"
            f"ID: {user.user_id}\n"
            f"Username: {username}\n"
            f"Имя: {user.full_name}\n"
            f"Текущая роль: {role_text}",
            reply_markup=role_menu(user.user_id),
        )
        return

    await send_user_card(message, user)


async def send_user_card(event, user: User):
    sub_status = "✅ Активна" if user.has_subscription else "❌ Не активна"
    role_text = {
        "user": "👤 Пользователь",
        "moderator": "🛡 Модератор",
        "admin": "⚙️ Администратор",
        "banned": "🚫 Заблокирован"
    }.get(user.role, user.role)

    created = user.created_at.strftime("%d.%m.%Y")
    username = f"@{user.username}" if user.username else "нет"
    now = datetime.now()

    async with async_session() as session:
        protection_state = await session.scalar(
            select(ContentProtectionState).where(ContentProtectionState.user_id == user.user_id)
        )
        views_hour = int(await session.scalar(
            select(func.count(ContentStat.id)).where(
                ContentStat.user_id == user.user_id,
                ContentStat.clicked_at >= now - timedelta(hours=1),
            )
        ) or 0)

    content_blocked = bool(
        protection_state
        and protection_state.blocked_until
        and protection_state.blocked_until > now
    )
    if content_blocked:
        protection_text = f"⏳ до {protection_state.blocked_until:%d.%m.%Y %H:%M:%S}"
    else:
        protection_text = "✅ ограничений нет"

    warning_count = int(protection_state.warning_count or 0) if protection_state else 0
    last_reason = protection_state.last_reason if protection_state and protection_state.last_reason else "—"

    text = (
        f"👤 Пользователь\n\n"
        f"ID: {user.user_id}\n"
        f"Username: {username}\n"
        f"Имя: {user.full_name}\n"
        f"Роль: {role_text}\n"
        f"Подписка: {sub_status}\n"
        f"Дата регистрации: {created}\n\n"
        f"🛡 Защита контента\n"
        f"Код лицензии: {make_license_code(user.user_id)}\n"
        f"Открытий за час: {views_hour}\n"
        f"Защитная пауза: {protection_text}\n"
        f"Срабатываний: {warning_count}\n"
        f"Последняя причина: {last_reason}"
    )

    keyboard = user_card_menu(
        user.user_id,
        user.has_subscription,
        user.role,
        content_blocked=content_blocked,
    )

    if isinstance(event, Message):
        await event.answer(text, reply_markup=keyboard)
    else:
        await event.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("admin:sub_give:"))
async def admin_sub_give(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.has_subscription = True
            user.subscription_date = datetime.now()
            await session.commit()
    await callback.answer("✅ Подписка выдана")
    async with async_session() as session:
        user = await get_user(session, user_id)
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:sub_remove:"))
async def admin_sub_remove(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.has_subscription = False
            await session.commit()
    await callback.answer("❌ Подписка забрана")
    async with async_session() as session:
        user = await get_user(session, user_id)
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:content_unblock:"))
async def admin_content_unblock(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[2])
    await clear_content_block(user_id)
    await callback.answer("✅ Защитная пауза снята")

    async with async_session() as session:
        user = await get_user(session, user_id)
    if user:
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:role_change:"))
async def admin_role_change(callback: CallbackQuery):
    if not await is_superadmin(callback.from_user.id):
        await callback.answer("Только главный админ может менять роли", show_alert=True)
        return
    user_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        "🎭 Выбери новую роль:",
        reply_markup=role_menu(user_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:set_role:"))
async def admin_set_role(callback: CallbackQuery):
    if not await is_superadmin(callback.from_user.id):
        await callback.answer("Только главный админ может менять роли", show_alert=True)
        return
    parts = callback.data.split(":")
    user_id = int(parts[2])
    new_role = parts[3]
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.role = new_role
            await session.commit()
    await callback.answer(f"✅ Роль изменена")
    async with async_session() as session:
        user = await get_user(session, user_id)
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:ban:"))
async def admin_ban(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.role = "banned"
            await session.commit()
    await callback.answer("🚫 Пользователь забанен")
    async with async_session() as session:
        user = await get_user(session, user_id)
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:unban:"))
async def admin_unban(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        user = await get_user(session, user_id)
        if user:
            user.role = "user"
            await session.commit()
    await callback.answer("✅ Пользователь разбанен")
    async with async_session() as session:
        user = await get_user(session, user_id)
        await send_user_card(callback, user)


@router.callback_query(F.data.startswith("admin:users_list:"))
async def admin_users_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    category = parts[2]
    page = int(parts[3])
    limit = 10
    offset = page * limit

    async with async_session() as session:
        if category == "admins":
            query = select(User).where(User.role.in_(["admin", "moderator"]))
            count_query = select(func.count()).select_from(User).where(User.role.in_(["admin", "moderator"]))
            title = "⚙️ Администраторы"
        elif category == "banned":
            query = select(User).where(User.role == "banned")
            count_query = select(func.count()).select_from(User).where(User.role == "banned")
            title = "🚫 Забаненные"
        else:
            query = select(User)
            count_query = select(func.count()).select_from(User)
            title = "👥 Все пользователи"

        total = await session.scalar(count_query)
        result = await session.execute(query.offset(offset).limit(limit))
        users = result.scalars().all()

        if not users:
            await callback.message.edit_text(
                f"{title}\n\nПусто",
                reply_markup=users_menu()
            )
            await callback.answer()
            return

        await callback.message.edit_text(
            f"{title}\n\nСтраница {page+1} • Всего: {total}",
            reply_markup=users_list_menu(users, category, page, total)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user_card:"))
async def admin_user_card(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    user_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        user = await get_user(session, user_id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        await send_user_card(callback, user)
    await callback.answer()
