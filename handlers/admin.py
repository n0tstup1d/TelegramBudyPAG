from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from datetime import datetime, timedelta
from states.states import WithdrawStates, BroadcastStates, ReferralSettings, PromoStates
from database.engine import async_session
from database.models import User, WithdrawalRequest, ReferralBalance
from database.crud import get_user
from database.settings import get_setting, set_setting, is_referral_enabled, get_referral_reward, get_min_withdrawal
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from states.states import BroadcastStates, ReferralSettings, AdminUserStates, PromoStates
from keyboards.menus import (
    admin_menu, users_menu, users_list_menu,
    user_card_menu, role_menu, find_user_menu,
    promo_menu, promo_list_menu, promo_card_menu
)
from database.models import User, WithdrawalRequest, ReferralBalance, PromoCode


router = Router()


# ——— Проверка роли ———

async def is_admin(user_id: int) -> bool:
    async with async_session() as session:
        user = await get_user(session, user_id)
        return user and user.role in ("admin", "moderator")


async def is_superadmin(user_id: int) -> bool:
    async with async_session() as session:
        user = await get_user(session, user_id)
        return user and user.role == "admin"


# ——— Главное меню админки ———

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="admin:referral")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="👤 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin:promo")],
        [InlineKeyboardButton(text="⚙️ Назначить роль", callback_data="admin:roles")],
    ])


# ——— Команда /admin ———

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return

    await message.answer(
        "🔧 Панель администратора",
        reply_markup=admin_menu()
    )


# ——— Статистика ———

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        # всего пользователей
        total = await session.scalar(select(func.count()).select_from(User))

        # платящих
        paid = await session.scalar(
            select(func.count()).select_from(User).where(User.has_subscription == True)
        )

        # новых за сегодня
        today = datetime.now().replace(hour=0, minute=0, second=0)
        today_new = await session.scalar(
            select(func.count()).select_from(User).where(User.created_at >= today)
        )

        # новых за неделю
        week_ago = datetime.now() - timedelta(days=7)
        week_new = await session.scalar(
            select(func.count()).select_from(User).where(User.created_at >= week_ago)
        )

        # новых за месяц
        month_ago = datetime.now() - timedelta(days=30)
        month_new = await session.scalar(
            select(func.count()).select_from(User).where(User.created_at >= month_ago)
        )

        # заявки на вывод
        pending_withdrawals = await session.scalar(
            select(func.count()).select_from(WithdrawalRequest)
            .where(WithdrawalRequest.status == "pending")
        )

        text = (
            f"📊 Статистика\n\n"
            f"👥 Всего пользователей: {total}\n"
            f"💳 Платящих: {paid}\n"
            f"📈 Конверсия: {round(paid / total * 100, 1) if total else 0}%\n\n"
            f"🆕 Новых сегодня: {today_new}\n"
            f"🆕 Новых за неделю: {week_new}\n"
            f"🆕 Новых за месяц: {month_new}\n\n"
            f"💸 Заявок на вывод: {pending_withdrawals}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")]
            ])
        )
    await callback.answer()


# ——— Заявки на вывод ———

@router.callback_query(F.data == "admin:withdrawals")
async def admin_withdrawals(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(
            select(WithdrawalRequest)
            .where(WithdrawalRequest.status.in_(["pending", "processing"]))
            .order_by(WithdrawalRequest.requested_at)
        )
        requests = result.scalars().all()

        if not requests:
            await callback.message.edit_text(
                "✅ Заявок на вывод нет",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")]
                ])
            )
            await callback.answer()
            return

        buttons = []
        for req in requests:
            status_icon = "🟡" if req.status == "pending" else "🔵"
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_icon} #{req.id} — {req.amount} ₽",
                    callback_data=f"admin:withdrawal:{req.id}"
                )
            ])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")])

        await callback.message.edit_text(
            "💸 Заявки на вывод:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:withdrawal:"))
async def admin_withdrawal_detail(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    request_id = int(callback.data.split(":")[2])

    async with async_session() as session:
        request = await session.get(WithdrawalRequest, request_id)
        if not request:
            await callback.answer("Заявка не найдена", show_alert=True)
            return

        user = await get_user(session, request.user_id)
        username = f"@{user.username}" if user and user.username else str(request.user_id)

        status_text = {
            "pending": "🟡 Ожидает",
            "processing": f"🔵 В обработке у {request.taken_by}",
            "completed": "✅ Выполнена",
            "cancelled": "❌ Отменена"
        }.get(request.status, request.status)

        text = (
            f"💸 Заявка #{request.id}\n\n"
            f"👤 Пользователь: {username}\n"
            f"💰 Сумма: {request.amount} ₽\n"
            f"📅 Создана: {request.requested_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"Статус: {status_text}"
        )

        buttons = []
        if request.status == "pending":
            buttons.append([
                InlineKeyboardButton(
                    text="🔵 Взять в работу",
                    callback_data=f"admin:take:{request_id}"
                )
            ])
        elif request.status == "processing" and request.taken_by == callback.from_user.id:
            buttons.append([
                InlineKeyboardButton(
                    text="✅ Подтвердить перевод",
                    callback_data=f"admin:complete:{request_id}"
                )
            ])
            buttons.append([
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"admin:cancel_withdrawal:{request_id}"
                )
            ])

        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:withdrawals")])

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:take:"))
async def admin_take_withdrawal(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    request_id = int(callback.data.split(":")[2])

    async with async_session() as session:
        request = await session.get(WithdrawalRequest, request_id)

        if request.status != "pending":
            await callback.answer("Заявка уже взята в работу!", show_alert=True)
            return

        request.status = "processing"
        request.taken_by = callback.from_user.id
        await session.commit()

        await callback.answer("✅ Заявка взята в работу")
        await admin_withdrawal_detail(callback)


@router.callback_query(F.data.startswith("admin:complete:"))
async def admin_complete_withdrawal(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    request_id = int(callback.data.split(":")[2])

    async with async_session() as session:
        request = await session.get(WithdrawalRequest, request_id)

        if request.taken_by != callback.from_user.id:
            await callback.answer("Это не твоя заявка!", show_alert=True)
            return

        request.status = "completed"
        request.completed_at = datetime.now()

        # размораживаем и обнуляем
        result = await session.execute(
            select(ReferralBalance).where(ReferralBalance.user_id == request.user_id)
        )
        balance = result.scalar_one_or_none()
        if balance:
            balance.frozen = 0
        await session.commit()

        # уведомляем пользователя
        await callback.bot.send_message(
            request.user_id,
            f"✅ Деньги отправлены!\n\n"
            f"Сумма: {request.amount} ₽\n"
            f"Заявка #{request.id}\n\n"
            f"Если деньги не пришли — напиши в поддержку."
        )

    await callback.answer("✅ Перевод подтверждён")
    await callback.message.edit_text(
        "✅ Заявка выполнена, пользователь уведомлён.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К заявкам", callback_data="admin:withdrawals")]
        ])
    )


@router.callback_query(F.data.startswith("admin:cancel_withdrawal:"))
async def admin_cancel_withdrawal(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    request_id = int(callback.data.split(":")[2])

    async with async_session() as session:
        request = await session.get(WithdrawalRequest, request_id)
        request.status = "cancelled"

        # возвращаем баланс
        result = await session.execute(
            select(ReferralBalance).where(ReferralBalance.user_id == request.user_id)
        )
        balance = result.scalar_one_or_none()
        if balance:
            balance.balance = balance.frozen
            balance.frozen = 0
        await session.commit()

        await callback.bot.send_message(
            request.user_id,
            f"❌ Заявка на вывод #{request.id} отменена.\n\n"
            f"Средства возвращены на баланс.\n"
            f"Если это ошибка — напиши в поддержку."
        )

    await callback.answer("Заявка отменена")
    await callback.message.edit_text(
        "❌ Заявка отменена, средства возвращены.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К заявкам", callback_data="admin:withdrawals")]
        ])
    )


@router.callback_query(F.data == "admin:menu")
async def admin_back(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🔧 Панель администратора",
        reply_markup=admin_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "admin:referral")
async def admin_referral(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        enabled = await is_referral_enabled(session)
        reward = await get_referral_reward(session)
        min_w = await get_min_withdrawal(session)

        # статистика
        total_referrals = await session.scalar(
            select(func.count()).select_from(User).where(User.referred_by.isnot(None))
        )
        total_paid = await session.scalar(
            select(func.sum(ReferralBalance.total_earned)).select_from(ReferralBalance)
        ) or 0
        total_frozen = await session.scalar(
            select(func.sum(ReferralBalance.frozen)).select_from(ReferralBalance)
        ) or 0

        # топ рефереров
        top_result = await session.execute(
            select(User.username, User.user_id, func.count(User.referred_by).label("count"))
            .join(User, User.referred_by == User.user_id, isouter=True)
            .group_by(User.username, User.user_id)
            .order_by(func.count(User.referred_by).desc())
            .limit(3)
        )
        top = top_result.all()

        top_text = ""
        for i, row in enumerate(top, 1):
            name = f"@{row.username}" if row.username else str(row.user_id)
            top_text += f"{i}. {name} — {row.count} чел.\n"

        status = "✅ Включена" if enabled else "❌ Выключена"
        toggle_text = "❌ Выключить" if enabled else "✅ Включить"
        toggle_value = "false" if enabled else "true"

        text = (
            f"👥 Реферальная система\n\n"
            f"Статус: {status}\n"
            f"Награда за реферала: {reward} ₽\n"
            f"Минимум для вывода: {min_w} ₽\n\n"
            f"📊 Статистика:\n"
            f"Всего рефералов: {total_referrals}\n"
            f"Выплачено всего: {total_paid} ₽\n"
            f"Заморожено: {total_frozen} ₽\n\n"
            f"🏆 Топ рефереров:\n{top_text if top_text else 'Пока нет'}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"admin:referral_toggle:{toggle_value}"
                )],
                [InlineKeyboardButton(
                    text="✏️ Изменить награду",
                    callback_data="admin:referral_reward"
                )],
                [InlineKeyboardButton(
                    text="✏️ Изменить минимум вывода",
                    callback_data="admin:referral_minw"
                )],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")]
            ])
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:referral_toggle:"))
async def admin_referral_toggle(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    value = callback.data.split(":")[2]
    async with async_session() as session:
        await set_setting(session, "referral_enabled", value)

    await callback.answer("✅ Настройка изменена")
    await admin_referral(callback)


class ReferralSettings(StatesGroup):
    waiting_reward = State()
    waiting_minw = State()


@router.callback_query(F.data == "admin:referral_reward")
async def admin_change_reward(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(ReferralSettings.waiting_reward)
    await callback.message.edit_text(
        "✏️ Введи новую сумму награды за реферала (в рублях):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:referral")]
        ])
    )
    await callback.answer()


@router.message(ReferralSettings.waiting_reward)
async def admin_save_reward(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    if not message.text.isdigit():
        await message.answer("⚠️ Введи число")
        return

    async with async_session() as session:
        await set_setting(session, "referral_reward", message.text)

    await state.clear()
    await message.answer(f"✅ Награда изменена на {message.text} ₽")


@router.callback_query(F.data == "admin:referral_minw")
async def admin_change_minw(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(ReferralSettings.waiting_minw)
    await callback.message.edit_text(
        "✏️ Введи новый минимум для вывода (в рублях):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:referral")]
        ])
    )
    await callback.answer()


@router.message(ReferralSettings.waiting_minw)
async def admin_save_minw(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    if not message.text.isdigit():
        await message.answer("⚠️ Введи число")
        return

    async with async_session() as session:
        await set_setting(session, "min_withdrawal", message.text)

    await state.clear()
    await message.answer(f"✅ Минимум вывода изменён на {message.text} ₽")



class BroadcastStates(StatesGroup):
    waiting_audience = State()
    waiting_message = State()
    waiting_button = State()
    confirm = State()


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "📢 Рассылка\n\nВыбери аудиторию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Все пользователи", callback_data="broadcast:all")],
            [InlineKeyboardButton(text="💳 Только подписчики", callback_data="broadcast:paid")],
            [InlineKeyboardButton(text="🆓 Без подписки", callback_data="broadcast:free")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:"))
async def broadcast_audience(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    audience = callback.data.split(":")[1]
    if audience == "admin":
        return

    audience_text = {
        "all": "все пользователи",
        "paid": "только подписчики",
        "free": "без подписки"
    }.get(audience)

    await state.set_state(BroadcastStates.waiting_message)
    await state.update_data(audience=audience)

    await callback.message.edit_text(
        f"📢 Аудитория: {audience_text}\n\n"
        f"Напиши текст сообщения для рассылки.\n\n"
        f"Можно использовать:\n"
        f"*жирный* _курсив_ `код`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:broadcast")]
        ])
    )
    await callback.answer()


@router.message(BroadcastStates.waiting_message)
async def broadcast_message(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    await state.update_data(
        text=message.text or message.caption,
        photo=message.photo[-1].file_id if message.photo else None
    )
    await state.set_state(BroadcastStates.waiting_button)

    await message.answer(
        "Хочешь добавить кнопку к сообщению?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="broadcast:add_button")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="broadcast:no_button")]
        ])
    )


@router.callback_query(F.data == "broadcast:no_button")
async def broadcast_no_button(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.update_data(button_text=None, button_url=None)
    await show_broadcast_preview(callback, state)
    await callback.answer()


@router.callback_query(F.data == "broadcast:add_button")
async def broadcast_add_button(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(BroadcastStates.waiting_button)
    await callback.message.answer(
        "Напиши текст кнопки и ссылку через символ | \n\n"
        "Например:\n"
        "Перейти на сайт | https://example.com",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:broadcast")]
        ])
    )
    await callback.answer()


@router.message(BroadcastStates.waiting_button)
async def broadcast_button(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    try:
        parts = message.text.split("|")
        if len(parts) != 2:
            raise ValueError
        btn_text = parts[0].strip()
        btn_url = parts[1].strip()
        if not btn_url.startswith("http"):
            raise ValueError
        await state.update_data(button_text=btn_text, button_url=btn_url)
    except ValueError:
        await message.answer(
            "⚠️ Неверный формат. Используй:\n"
            "Текст кнопки | https://ссылка"
        )
        return

    await show_broadcast_preview(message, state)


async def show_broadcast_preview(event, state: FSMContext):
    data = await state.get_data()
    text = data.get("text")
    audience = data.get("audience")
    button_text = data.get("button_text")
    button_url = data.get("button_url")

    audience_text = {
        "all": "все пользователи",
        "paid": "только подписчики",
        "free": "без подписки"
    }.get(audience)

    preview = f"📢 Предпросмотр рассылки\n\nАудитория: {audience_text}\n\n{text}"

    keyboard = []
    if button_text and button_url:
        keyboard.append([InlineKeyboardButton(text=button_text, url=button_url)])

    keyboard.append([InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast:send")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin:broadcast")])

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(
            preview,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    else:
        await event.answer(
            preview,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )

    await state.set_state(BroadcastStates.confirm)


@router.callback_query(F.data == "broadcast:send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    text = data.get("text")
    audience = data.get("audience")
    button_text = data.get("button_text")
    button_url = data.get("button_url")

    keyboard = None
    if button_text and button_url:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=button_text, url=button_url)]
        ])

    async with async_session() as session:
        query = select(User.user_id)
        if audience == "paid":
            query = query.where(User.has_subscription == True)
        elif audience == "free":
            query = query.where(User.has_subscription == False)

        result = await session.execute(query)
        user_ids = result.scalars().all()

    await callback.message.edit_text(f"📢 Рассылка запущена... 0/{len(user_ids)}")

    success = 0
    failed = 0

    for user_id in user_ids:
        try:
            await callback.bot.send_message(
                user_id,
                text,
                reply_markup=keyboard
            )
            success += 1
        except Exception:
            failed += 1

    await state.clear()
    await callback.message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"Отправлено: {success}\n"
        f"Ошибок: {failed}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В админку", callback_data="admin:menu")]
        ])
    )

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
    await callback.message.edit_text(
        "🔍 Введи username (@username) или Telegram ID:",
        reply_markup=find_user_menu()
    )
    await callback.answer()


@router.message(AdminUserStates.waiting_user_id)
async def admin_user_search(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

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

    text = (
        f"👤 Пользователь\n\n"
        f"ID: {user.user_id}\n"
        f"Username: {username}\n"
        f"Имя: {user.full_name}\n"
        f"Роль: {role_text}\n"
        f"Подписка: {sub_status}\n"
        f"Дата регистрации: {created}"
    )

    keyboard = user_card_menu(user.user_id, user.has_subscription, user.role)

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



@router.callback_query(F.data == "admin:promo")
async def admin_promo(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🎟 Промокоды",
        reply_markup=promo_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promo_list")
async def admin_promo_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))
        promos = result.scalars().all()

    if not promos:
        await callback.message.edit_text(
            "🎟 Промокодов пока нет",
            reply_markup=promo_menu()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🎟 Список промокодов:",
        reply_markup=promo_list_menu(promos)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_card:"))
async def admin_promo_card(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    promo_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        promo = await session.get(PromoCode, promo_id)
        if not promo:
            await callback.answer("Промокод не найден", show_alert=True)
            return

        status = "✅ Активен" if promo.is_active else "❌ Выключен"
        text = (
            f"🎟 Промокод: {promo.code}\n\n"
            f"💰 Скидка: {promo.discount} ₽\n"
            f"📊 Использований: {promo.used_count}/{promo.usage_limit}\n"
            f"Статус: {status}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=promo_card_menu(promo_id, promo.is_active)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:promo_toggle:"))
async def admin_promo_toggle(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    promo_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        promo = await session.get(PromoCode, promo_id)
        if promo:
            promo.is_active = not promo.is_active
            await session.commit()
            await callback.answer("✅ Статус изменён")
            await admin_promo_card(callback)


@router.callback_query(F.data.startswith("admin:promo_delete:"))
async def admin_promo_delete(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    promo_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        promo = await session.get(PromoCode, promo_id)
        if promo:
            await session.delete(promo)
            await session.commit()

    await callback.answer("🗑 Промокод удалён")
    await callback.message.edit_text(
        "🎟 Промокоды",
        reply_markup=promo_menu()
    )


@router.callback_query(F.data == "admin:promo_create")
async def admin_promo_create(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(PromoStates.waiting_code)
    await callback.message.edit_text(
        "🎟 Создание промокода\n\n"
        "Введи код промокода (только латиница и цифры):\n"
        "Например: HEALTH20",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo")]
        ])
    )
    await callback.answer()


@router.message(PromoStates.waiting_code)
async def admin_promo_code(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    code = message.text.strip().upper()

    async with async_session() as session:
        result = await session.execute(
            select(PromoCode).where(PromoCode.code == code)
        )
        exists = result.scalar_one_or_none()

    if exists:
        await message.answer("⚠️ Такой промокод уже существует. Введи другой:")
        return

    await state.update_data(code=code)
    await state.set_state(PromoStates.waiting_discount)
    await message.answer(
        f"✅ Код: {code}\n\nВведи размер скидки в рублях:"
    )


@router.message(PromoStates.waiting_discount)
async def admin_promo_discount(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    if not message.text.isdigit():
        await message.answer("⚠️ Введи число")
        return

    await state.update_data(discount=int(message.text))
    await state.set_state(PromoStates.waiting_limit)
    await message.answer("Введи лимит использований (сколько раз можно применить):")


@router.message(PromoStates.waiting_limit)
async def admin_promo_limit(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    if not message.text.isdigit():
        await message.answer("⚠️ Введи число")
        return

    data = await state.get_data()
    await state.clear()

    async with async_session() as session:
        promo = PromoCode(
            code=data["code"],
            discount=data["discount"],
            usage_limit=int(message.text)
        )
        session.add(promo)
        await session.commit()

    await message.answer(
        f"✅ Промокод создан!\n\n"
        f"Код: {data['code']}\n"
        f"Скидка: {data['discount']} ₽\n"
        f"Лимит: {message.text} использований",
        reply_markup=promo_menu()
    )

from states.states import BroadcastStates, ReferralSettings, AdminUserStates, PromoStates, ShopStates
from keyboards.menus import (
    admin_menu, users_menu, users_list_menu,
    user_card_menu, role_menu, find_user_menu,
    promo_menu, promo_list_menu, promo_card_menu,
    admin_shops_menu, admin_shop_card_menu
)
from database.models import User, WithdrawalRequest, ReferralBalance, PromoCode, Shop, ShopClick


@router.callback_query(F.data == "admin:shops")
async def admin_shops(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "🏪 Управление магазинами",
        reply_markup=admin_shops_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "admin:shop_list")
async def admin_shop_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(select(Shop).order_by(Shop.created_at.desc()))
        shops = result.scalars().all()

    if not shops:
        await callback.message.edit_text(
            "🏪 Магазинов пока нет",
            reply_markup=admin_shops_menu()
        )
        await callback.answer()
        return

    buttons = []
    for shop in shops:
        status = "✅" if shop.is_active else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {shop.name} ({shop.country})",
                callback_data=f"admin:shop_card:{shop.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:shops")])

    await callback.message.edit_text(
        "🏪 Список магазинов:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:shop_card:"))
async def admin_shop_card(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    shop_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        shop = await session.get(Shop, shop_id)
        if not shop:
            await callback.answer("Магазин не найден", show_alert=True)
            return

        clicks = await session.scalar(
            select(func.count()).select_from(ShopClick).where(ShopClick.shop_id == shop_id)
        )

        status = "✅ Активен" if shop.is_active else "❌ Выключен"
        text = (
            f"🏪 {shop.name}\n\n"
            f"🌍 Страна: {shop.country}\n"
            f"🔗 URL: {shop.url}\n"
            f"📊 Кликов: {clicks}\n"
            f"Статус: {status}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=admin_shop_card_menu(shop_id, shop.is_active)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:shop_toggle:"))
async def admin_shop_toggle(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    shop_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        shop = await session.get(Shop, shop_id)
        if shop:
            shop.is_active = not shop.is_active
            await session.commit()
    await callback.answer("✅ Статус изменён")
    await admin_shop_card(callback)


@router.callback_query(F.data.startswith("admin:shop_delete:"))
async def admin_shop_delete(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return

    shop_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        shop = await session.get(Shop, shop_id)
        if shop:
            await session.delete(shop)
            await session.commit()

    await callback.answer("🗑 Магазин удалён")
    await callback.message.edit_text(
        "🏪 Управление магазинами",
        reply_markup=admin_shops_menu()
    )


@router.callback_query(F.data == "admin:shop_add")
async def admin_shop_add(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return

    await state.set_state(ShopStates.waiting_name)
    await callback.message.edit_text(
        "🏪 Добавление магазина\n\nВведи название магазина:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:shops")]
        ])
    )
    await callback.answer()


@router.message(ShopStates.waiting_name)
async def admin_shop_name(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    await state.update_data(name=message.text.strip())
    await state.set_state(ShopStates.waiting_country)
    await message.answer("Введи страну (например: RU, KZ, KG):")


@router.message(ShopStates.waiting_country)
async def admin_shop_country(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    await state.update_data(country=message.text.strip().upper())
    await state.set_state(ShopStates.waiting_url)
    await message.answer("Введи реферальную ссылку на магазин:")


@router.message(ShopStates.waiting_url)
async def admin_shop_url(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return

    data = await state.get_data()
    await state.clear()

    async with async_session() as session:
        shop = Shop(
            name=data["name"],
            country=data["country"],
            url=message.text.strip()
        )
        session.add(shop)
        await session.commit()

    await message.answer(
        f"✅ Магазин добавлен!\n\n"
        f"🏪 {data['name']}\n"
        f"🌍 {data['country']}\n"
        f"🔗 {message.text.strip()}",
        reply_markup=admin_shops_menu()
    )