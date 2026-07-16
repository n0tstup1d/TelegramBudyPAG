from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import (
    ALLOW_MEMORY_STORAGE,
    BOT_TOKEN,
    DROP_PENDING_UPDATES,
    REDIS_URL,
    PAYMENTS_ENABLED,
    RECEIPT_REMINDERS_ENABLED,
    CONTENT_MARK_SECRET,
    CONTENT_PROTECTION_ENABLED,
)
from database.engine import async_session, engine
from database.settings import apply_security_defaults
from middlewares.rate_limit import RateLimitMiddleware
from middlewares.subscription import SubscriptionMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def build_storage() -> BaseStorage:
    if REDIS_URL:
        try:
            from aiogram.fsm.storage.redis import RedisStorage
        except ImportError as exc:
            raise RuntimeError(
                "Задан REDIS_URL, но не установлен пакет redis. Выполните: pip install -r requirements.txt"
            ) from exc
        logger.info("FSM storage: Redis")
        return RedisStorage.from_url(REDIS_URL)

    if not ALLOW_MEMORY_STORAGE:
        raise RuntimeError(
            "REDIS_URL не задан, а ALLOW_MEMORY_STORAGE=false. "
            "Для продакшена настройте Redis, чтобы состояния не терялись после перезапуска."
        )

    logger.warning(
        "FSM storage: MemoryStorage. Состояния поддержки и форм будут потеряны после перезапуска. "
        "Для продакшена задайте REDIS_URL."
    )
    return MemoryStorage()


async def on_startup(bot: Bot) -> None:
    if CONTENT_PROTECTION_ENABLED and not CONTENT_MARK_SECRET:
        logger.warning(
            "CONTENT_MARK_SECRET не задан: коды лицензий временно используют BOT_TOKEN как fallback. "
            "Для независимой защиты задайте отдельный длинный секрет в .env."
        )

    async with async_session() as session:
        changed = await apply_security_defaults(session)
        if changed:
            logger.warning("Реферальная система и магазины отключены безопасным обновлением; включаются через /admin")

    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть VEGA"),
        BotCommand(command="product", description="Описание продукта"),
        BotCommand(command="buy", description="Условия покупки"),
        BotCommand(command="offer", description="Публичная оферта"),
        BotCommand(command="privacy", description="Обработка данных"),
        BotCommand(command="seller", description="Реквизиты и поддержка"),
    ])
    logger.info("Бот запущен")


async def main() -> None:
    if PAYMENTS_ENABLED:
        from services.yookassa import is_yookassa_configured
        if not is_yookassa_configured():
            raise RuntimeError(
                "PAYMENTS_ENABLED=true, но не заданы YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY"
            )

    bot = Bot(token=BOT_TOKEN)
    storage = build_storage()
    dp = Dispatcher(storage=storage)

    # Антиспам выполняется раньше проверки доступа.
    dp.message.outer_middleware(RateLimitMiddleware())
    dp.callback_query.outer_middleware(RateLimitMiddleware())

    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    dp.startup.register(on_startup)

    from handlers.user import router as user_router
    from handlers.admin import router as admin_router

    dp.include_router(user_router)
    dp.include_router(admin_router)

    background_tasks: list[asyncio.Task] = []
    if PAYMENTS_ENABLED:
        from services.payments import payment_reconciliation_loop
        background_tasks.append(asyncio.create_task(payment_reconciliation_loop(bot)))

        if RECEIPT_REMINDERS_ENABLED:
            from services.receipts import receipt_reminder_loop
            background_tasks.append(asyncio.create_task(receipt_reminder_loop(bot)))

    try:
        await bot.delete_webhook(drop_pending_updates=DROP_PENDING_UPDATES)
        await dp.start_polling(bot, close_bot_session=False)
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("Бот остановлен")
        await storage.close()
        await engine.dispose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
