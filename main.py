import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database.engine import engine
from database.models import Base
from middlewares.subscription import SubscriptionMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    logger.info("Бот запущен")


async def on_shutdown(bot: Bot):
    logger.info("Бот остановлен")
    await engine.dispose()


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # подключаем middleware
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    from handlers.start import router as start_router
    from handlers.content import router as content_router
    from handlers.profile import router as profile_router
    from handlers.admin import router as admin_router
    from handlers.shops import router as shops_router

    dp.include_router(shops_router)
    dp.include_router(start_router)
    dp.include_router(content_router)
    dp.include_router(profile_router)
    dp.include_router(admin_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())