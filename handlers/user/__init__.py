from aiogram import Router

from .shops import router as shops_router
from .support import router as support_router
from .start import router as start_router
from .content import router as content_router
from .profile import router as profile_router
from .referral import router as referral_router

router = Router()

# Магазины подключаем до content: там есть общий обработчик section:*.
router.include_router(shops_router)
router.include_router(support_router)
router.include_router(start_router)
router.include_router(content_router)
router.include_router(profile_router)
router.include_router(referral_router)
