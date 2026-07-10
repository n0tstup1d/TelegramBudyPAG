from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy import select, func, distinct

from database.engine import async_session
from database.models import (
    User,
    Transaction,
    PromoCode,
    Shop,
    ShopClick,
    ContentStat,
    ReferralBalance,
    WithdrawalRequest,
)
from database.settings import is_referral_enabled, get_referral_reward, get_min_withdrawal
from handlers.admin.guards import is_admin
from keyboards.admin.stats import stats_menu

router = Router()


async def safe_answer(callback: CallbackQuery, *args: Any, **kwargs: Any) -> None:
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest:
        pass


def pct(part: int | float | None, total: int | float | None) -> str:
    if not total:
        return "0%"
    return f"{round((part or 0) / total * 100, 1)}%"


def money(value: int | float | None) -> str:
    return f"{int(value or 0)} ₽"


def fmt_dt(value) -> str:
    if not value:
        return "—"
    try:
        return value.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(value)


async def scalar(session, stmt, default=0):
    value = await session.scalar(stmt)
    return default if value is None else value


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    await show_stats_page(callback, page="overview")


@router.callback_query(F.data.startswith("admin:stats:"))
async def admin_stats_page(callback: CallbackQuery):
    page = callback.data.split(":", 2)[2]
    await show_stats_page(callback, page=page)


async def show_stats_page(callback: CallbackQuery, page: str):
    if not await is_admin(callback.from_user.id):
        return

    await safe_answer(callback)

    builders = {
        "overview": build_overview_stats,
        "users": build_user_stats,
        "finance": build_finance_stats,
        "referral": build_referral_stats,
        "withdrawals": build_withdrawal_stats,
        "shops": build_shop_stats,
        "promos": build_promo_stats,
        "content": build_content_stats,
    }

    builder = builders.get(page, build_overview_stats)
    active = page if page in builders else "overview"

    async with async_session() as session:
        text = await builder(session)

    await callback.message.edit_text(text, reply_markup=stats_menu(active))


async def build_overview_stats(session) -> str:
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total = await scalar(session, select(func.count()).select_from(User))
    paid_users = await scalar(session, select(func.count()).select_from(User).where(User.has_subscription == True))
    free_users = await scalar(session, select(func.count()).select_from(User).where(User.has_subscription == False, User.role != "banned"))
    banned = await scalar(session, select(func.count()).select_from(User).where(User.role == "banned"))
    new_today = await scalar(session, select(func.count()).select_from(User).where(User.created_at >= today))
    new_week = await scalar(session, select(func.count()).select_from(User).where(User.created_at >= week_ago))
    new_month = await scalar(session, select(func.count()).select_from(User).where(User.created_at >= month_ago))

    revenue_total = await scalar(
        session,
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.paid == True),
    )
    revenue_month = await scalar(
        session,
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.paid == True, Transaction.created_at >= month_ago),
    )
    payments_count = await scalar(session, select(func.count()).select_from(Transaction).where(Transaction.paid == True))

    pending_withdrawals = await scalar(
        session,
        select(func.count()).select_from(WithdrawalRequest).where(WithdrawalRequest.status == "pending"),
    )
    pending_sum = await scalar(
        session,
        select(func.coalesce(func.sum(WithdrawalRequest.amount), 0)).where(WithdrawalRequest.status == "pending"),
    )

    referral_enabled = await is_referral_enabled(session)
    total_referrals = await scalar(session, select(func.count()).select_from(User).where(User.referred_by.isnot(None)))

    active_shops = await scalar(session, select(func.count()).select_from(Shop).where(Shop.is_active == True))
    shop_clicks = await scalar(session, select(func.count()).select_from(ShopClick))
    content_clicks = await scalar(session, select(func.count()).select_from(ContentStat))
    active_promos = await scalar(session, select(func.count()).select_from(PromoCode).where(PromoCode.is_active == True))
    promo_uses = await scalar(session, select(func.coalesce(func.sum(PromoCode.used_count), 0)))

    return (
        "📊 Статистика: обзор\n\n"
        "👥 Пользователи\n"
        f"Всего: {total}\n"
        f"Платящих: {paid_users}\n"
        f"Без подписки: {free_users}\n"
        f"Забанено: {banned}\n"
        f"Конверсия в оплату: {pct(paid_users, total)}\n\n"
        "🆕 Регистрации\n"
        f"Сегодня: {new_today}\n"
        f"За 7 дней: {new_week}\n"
        f"За 30 дней: {new_month}\n\n"
        "💳 Деньги\n"
        f"Оплат: {payments_count}\n"
        f"Выручка всего: {money(revenue_total)}\n"
        f"Выручка за 30 дней: {money(revenue_month)}\n\n"
        "👥 Рефералка\n"
        f"Статус: {'✅ включена' if referral_enabled else '❌ выключена'}\n"
        f"Реферальных пользователей: {total_referrals}\n\n"
        "💸 Выводы\n"
        f"Ожидают: {pending_withdrawals}\n"
        f"Сумма ожидания: {money(pending_sum)}\n\n"
        "🏪 / 🎟 / 📚\n"
        f"Активных магазинов: {active_shops}\n"
        f"Кликов по магазинам: {shop_clicks}\n"
        f"Активных промокодов: {active_promos}\n"
        f"Использований промокодов: {promo_uses}\n"
        f"Кликов по контенту: {content_clicks}"
    )


async def build_user_stats(session) -> str:
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total = await scalar(session, select(func.count()).select_from(User))
    agreed = await scalar(session, select(func.count()).select_from(User).where(User.agreed_to_terms == True))
    paid = await scalar(session, select(func.count()).select_from(User).where(User.has_subscription == True))
    banned = await scalar(session, select(func.count()).select_from(User).where(User.role == "banned"))
    admins = await scalar(session, select(func.count()).select_from(User).where(User.role == "admin"))
    moderators = await scalar(session, select(func.count()).select_from(User).where(User.role == "moderator"))
    regular = await scalar(session, select(func.count()).select_from(User).where(User.role == "user"))

    new_today = await scalar(session, select(func.count()).select_from(User).where(User.created_at >= today))
    new_yesterday = await scalar(session, select(func.count()).select_from(User).where(User.created_at >= yesterday, User.created_at < today))
    new_week = await scalar(session, select(func.count()).select_from(User).where(User.created_at >= week_ago))
    new_month = await scalar(session, select(func.count()).select_from(User).where(User.created_at >= month_ago))

    referred = await scalar(session, select(func.count()).select_from(User).where(User.referred_by.isnot(None)))
    organic = max(total - referred, 0)

    recent_result = await session.execute(
        select(User.user_id, User.username, User.full_name, User.created_at, User.has_subscription)
        .order_by(User.created_at.desc())
        .limit(5)
    )
    recent = recent_result.all()
    recent_text = ""
    for row in recent:
        name = f"@{row.username}" if row.username else row.full_name
        sub = "💳" if row.has_subscription else "🆓"
        recent_text += f"{sub} {name} — {fmt_dt(row.created_at)}\n"

    return (
        "👥 Статистика: пользователи\n\n"
        f"Всего пользователей: {total}\n"
        f"Приняли соглашение: {agreed} ({pct(agreed, total)})\n"
        f"С подпиской: {paid} ({pct(paid, total)})\n"
        f"Органика: {organic}\n"
        f"По рефералке: {referred}\n\n"
        "🆕 Регистрации\n"
        f"Сегодня: {new_today}\n"
        f"Вчера: {new_yesterday}\n"
        f"За 7 дней: {new_week}\n"
        f"За 30 дней: {new_month}\n\n"
        "🎭 Роли\n"
        f"Пользователи: {regular}\n"
        f"Модераторы: {moderators}\n"
        f"Админы: {admins}\n"
        f"Забанены: {banned}\n\n"
        "🧾 Последние регистрации\n"
        f"{recent_text if recent_text else 'Пока нет данных'}"
    )


async def build_finance_stats(session) -> str:
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    paid_count = await scalar(session, select(func.count()).select_from(Transaction).where(Transaction.paid == True))
    unpaid_count = await scalar(session, select(func.count()).select_from(Transaction).where(Transaction.paid == False))
    revenue_total = await scalar(session, select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.paid == True))
    revenue_today = await scalar(session, select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.paid == True, Transaction.created_at >= today))
    revenue_week = await scalar(session, select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.paid == True, Transaction.created_at >= week_ago))
    revenue_month = await scalar(session, select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.paid == True, Transaction.created_at >= month_ago))
    avg_check = int(revenue_total / paid_count) if paid_count else 0

    subs_total = await scalar(session, select(func.count()).select_from(User).where(User.has_subscription == True))
    subs_today = await scalar(session, select(func.count()).select_from(User).where(User.has_subscription == True, User.subscription_date >= today))
    subs_week = await scalar(session, select(func.count()).select_from(User).where(User.has_subscription == True, User.subscription_date >= week_ago))
    subs_month = await scalar(session, select(func.count()).select_from(User).where(User.has_subscription == True, User.subscription_date >= month_ago))

    last_payment = await session.execute(
        select(Transaction.user_id, Transaction.amount, Transaction.created_at)
        .where(Transaction.paid == True)
        .order_by(Transaction.created_at.desc())
        .limit(5)
    )
    rows = last_payment.all()
    last_text = ""
    for row in rows:
        last_text += f"ID {row.user_id} — {money(row.amount)} — {fmt_dt(row.created_at)}\n"

    return (
        "💳 Статистика: подписки и деньги\n\n"
        "💰 Выручка\n"
        f"Всего: {money(revenue_total)}\n"
        f"Сегодня: {money(revenue_today)}\n"
        f"За 7 дней: {money(revenue_week)}\n"
        f"За 30 дней: {money(revenue_month)}\n"
        f"Средний чек: {money(avg_check)}\n\n"
        "🧾 Транзакции\n"
        f"Оплаченных: {paid_count}\n"
        f"Неоплаченных/созданных: {unpaid_count}\n\n"
        "💳 Подписки\n"
        f"Активных: {subs_total}\n"
        f"Выдано сегодня: {subs_today}\n"
        f"За 7 дней: {subs_week}\n"
        f"За 30 дней: {subs_month}\n\n"
        "Последние оплаты\n"
        f"{last_text if last_text else 'Пока нет оплат'}"
    )


async def build_referral_stats(session) -> str:
    enabled = await is_referral_enabled(session)
    reward = await get_referral_reward(session)
    min_w = await get_min_withdrawal(session)

    referred_users = await scalar(session, select(func.count()).select_from(User).where(User.referred_by.isnot(None)))
    referrers = await scalar(session, select(func.count(distinct(User.referred_by))).where(User.referred_by.isnot(None)))
    total_earned = await scalar(session, select(func.coalesce(func.sum(ReferralBalance.total_earned), 0)))
    available = await scalar(session, select(func.coalesce(func.sum(ReferralBalance.balance), 0)))
    frozen = await scalar(session, select(func.coalesce(func.sum(ReferralBalance.frozen), 0)))

    top_result = await session.execute(
        select(User.referred_by, func.count(User.id).label("count"))
        .where(User.referred_by.isnot(None))
        .group_by(User.referred_by)
        .order_by(func.count(User.id).desc())
        .limit(5)
    )
    top_rows = top_result.all()

    top_text = ""
    for i, row in enumerate(top_rows, 1):
        referrer = await session.scalar(select(User).where(User.user_id == row.referred_by))
        name = f"@{referrer.username}" if referrer and referrer.username else str(row.referred_by)
        balance = await session.scalar(select(ReferralBalance).where(ReferralBalance.user_id == row.referred_by))
        earned = balance.total_earned if balance else 0
        top_text += f"{i}. {name} — {row.count} чел. — {money(earned)}\n"

    return (
        "👥 Статистика: рефералка\n\n"
        f"Статус: {'✅ включена' if enabled else '❌ выключена'}\n"
        f"Награда за друга: {money(reward)}\n"
        f"Минимум вывода: {money(min_w)}\n\n"
        f"Приглашённых пользователей: {referred_users}\n"
        f"Пользователей, которые пригласили хотя бы 1 друга: {referrers}\n\n"
        "💰 Балансы\n"
        f"Начислено всего: {money(total_earned)}\n"
        f"Доступно к выводу: {money(available)}\n"
        f"В обработке/заморожено: {money(frozen)}\n\n"
        "🏆 Топ рефереров\n"
        f"{top_text if top_text else 'Пока нет рефералов'}"
    )


async def build_withdrawal_stats(session) -> str:
    statuses = ["pending", "processing", "completed", "cancelled"]
    labels = {
        "pending": "🟡 Ожидают",
        "processing": "🔵 В работе",
        "completed": "✅ Выполнены",
        "cancelled": "❌ Отменены",
    }

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total = await scalar(session, select(func.count()).select_from(WithdrawalRequest))
    amount_total = await scalar(session, select(func.coalesce(func.sum(WithdrawalRequest.amount), 0)))
    today_count = await scalar(session, select(func.count()).select_from(WithdrawalRequest).where(WithdrawalRequest.requested_at >= today))
    week_count = await scalar(session, select(func.count()).select_from(WithdrawalRequest).where(WithdrawalRequest.requested_at >= week_ago))
    month_count = await scalar(session, select(func.count()).select_from(WithdrawalRequest).where(WithdrawalRequest.requested_at >= month_ago))

    lines = ""
    for status in statuses:
        count = await scalar(session, select(func.count()).select_from(WithdrawalRequest).where(WithdrawalRequest.status == status))
        amount = await scalar(session, select(func.coalesce(func.sum(WithdrawalRequest.amount), 0)).where(WithdrawalRequest.status == status))
        lines += f"{labels[status]}: {count} / {money(amount)}\n"

    last_result = await session.execute(
        select(WithdrawalRequest.id, WithdrawalRequest.user_id, WithdrawalRequest.amount, WithdrawalRequest.status, WithdrawalRequest.requested_at)
        .order_by(WithdrawalRequest.requested_at.desc())
        .limit(5)
    )
    last_rows = last_result.all()
    last_text = ""
    for row in last_rows:
        last_text += f"#{row.id} • ID {row.user_id} • {money(row.amount)} • {row.status} • {fmt_dt(row.requested_at)}\n"

    return (
        "💸 Статистика: выводы\n\n"
        f"Всего заявок: {total}\n"
        f"Сумма всех заявок: {money(amount_total)}\n"
        f"Сегодня: {today_count}\n"
        f"За 7 дней: {week_count}\n"
        f"За 30 дней: {month_count}\n\n"
        "По статусам\n"
        f"{lines}\n"
        "Последние заявки\n"
        f"{last_text if last_text else 'Пока нет заявок'}"
    )


async def build_shop_stats(session) -> str:
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total = await scalar(session, select(func.count()).select_from(Shop))
    active = await scalar(session, select(func.count()).select_from(Shop).where(Shop.is_active == True))
    inactive = max(total - active, 0)
    clicks = await scalar(session, select(func.count()).select_from(ShopClick))
    clicks_today = await scalar(session, select(func.count()).select_from(ShopClick).where(ShopClick.clicked_at >= today))
    clicks_week = await scalar(session, select(func.count()).select_from(ShopClick).where(ShopClick.clicked_at >= week_ago))
    clicks_month = await scalar(session, select(func.count()).select_from(ShopClick).where(ShopClick.clicked_at >= month_ago))
    unique_users = await scalar(session, select(func.count(distinct(ShopClick.user_id))))

    top_result = await session.execute(
        select(Shop.name, func.count(ShopClick.id).label("clicks"))
        .join(ShopClick, ShopClick.shop_id == Shop.id)
        .group_by(Shop.id, Shop.name)
        .order_by(func.count(ShopClick.id).desc())
        .limit(5)
    )
    top_rows = top_result.all()
    top_text = ""
    for i, row in enumerate(top_rows, 1):
        top_text += f"{i}. {row.name} — {row.clicks} кликов\n"

    return (
        "🏪 Статистика: магазины\n\n"
        f"Всего магазинов: {total}\n"
        f"Активных: {active}\n"
        f"Выключенных: {inactive}\n\n"
        "Клики\n"
        f"Всего: {clicks}\n"
        f"Сегодня: {clicks_today}\n"
        f"За 7 дней: {clicks_week}\n"
        f"За 30 дней: {clicks_month}\n"
        f"Уникальных пользователей: {unique_users}\n\n"
        "🏆 Топ магазинов\n"
        f"{top_text if top_text else 'Пока нет кликов'}"
    )


async def build_promo_stats(session) -> str:
    total = await scalar(session, select(func.count()).select_from(PromoCode))
    active = await scalar(session, select(func.count()).select_from(PromoCode).where(PromoCode.is_active == True))
    inactive = max(total - active, 0)
    uses = await scalar(session, select(func.coalesce(func.sum(PromoCode.used_count), 0)))
    limits = await scalar(session, select(func.coalesce(func.sum(PromoCode.usage_limit), 0)))
    discounts = await scalar(session, select(func.coalesce(func.sum(PromoCode.discount), 0)))

    top_result = await session.execute(
        select(PromoCode.code, PromoCode.discount, PromoCode.used_count, PromoCode.usage_limit, PromoCode.is_active)
        .order_by(PromoCode.used_count.desc(), PromoCode.created_at.desc())
        .limit(7)
    )
    rows = top_result.all()
    top_text = ""
    for row in rows:
        status = "✅" if row.is_active else "❌"
        top_text += f"{status} {row.code} — {row.used_count}/{row.usage_limit} — скидка {money(row.discount)}\n"

    return (
        "🎟 Статистика: промокоды\n\n"
        f"Всего промокодов: {total}\n"
        f"Активных: {active}\n"
        f"Выключенных: {inactive}\n"
        f"Использований: {uses}/{limits}\n"
        f"Сумма скидок по номиналу: {money(discounts)}\n\n"
        "🏆 Промокоды по использованию\n"
        f"{top_text if top_text else 'Пока нет промокодов'}"
    )


async def build_content_stats(session) -> str:
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    clicks = await scalar(session, select(func.count()).select_from(ContentStat))
    clicks_today = await scalar(session, select(func.count()).select_from(ContentStat).where(ContentStat.clicked_at >= today))
    clicks_week = await scalar(session, select(func.count()).select_from(ContentStat).where(ContentStat.clicked_at >= week_ago))
    clicks_month = await scalar(session, select(func.count()).select_from(ContentStat).where(ContentStat.clicked_at >= month_ago))
    unique_users = await scalar(session, select(func.count(distinct(ContentStat.user_id))))
    unique_topics = await scalar(session, select(func.count(distinct(ContentStat.content_id))))

    top_result = await session.execute(
        select(ContentStat.content_id, func.count(ContentStat.id).label("clicks"))
        .group_by(ContentStat.content_id)
        .order_by(func.count(ContentStat.id).desc())
        .limit(10)
    )
    rows = top_result.all()
    top_text = ""
    for i, row in enumerate(rows, 1):
        top_text += f"{i}. {row.content_id} — {row.clicks}\n"

    return (
        "📚 Статистика: контент\n\n"
        f"Кликов всего: {clicks}\n"
        f"Сегодня: {clicks_today}\n"
        f"За 7 дней: {clicks_week}\n"
        f"За 30 дней: {clicks_month}\n"
        f"Уникальных пользователей: {unique_users}\n"
        f"Уникальных тем/действий: {unique_topics}\n\n"
        "🏆 Топ контента\n"
        f"{top_text if top_text else 'Пока нет кликов по контенту'}"
    )
