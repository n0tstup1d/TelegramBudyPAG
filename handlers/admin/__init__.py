from aiogram import Router

from .menu import router as menu_router
from .stats import router as stats_router
from .withdrawals import router as withdrawals_router
from .referral import router as referral_router
from .broadcast import router as broadcast_router
from .users import router as users_router
from .promos import router as promos_router
from .shops import router as shops_router

router = Router()

router.include_router(menu_router)
router.include_router(stats_router)
router.include_router(withdrawals_router)
router.include_router(referral_router)
router.include_router(broadcast_router)
router.include_router(users_router)
router.include_router(promos_router)
router.include_router(shops_router)
