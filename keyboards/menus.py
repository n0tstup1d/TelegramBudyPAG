# Deprecated compatibility layer. New code imports from keyboards.common, keyboards.user, keyboards.admin.
from keyboards.common import bottom_keyboard, terms_keyboard, pay_keyboard, banned_keyboard, support_keyboard
from keyboards.user import (
    SECTIONS, main_menu,
    section_menu, topic_menu, pages_menu, questions_menu, sources_menu, answer_menu,
    shops_menu, shop_card_menu,
    profile_keyboard, referral_keyboard, withdraw_cancel_keyboard, after_withdraw_keyboard,
)
from keyboards.admin import (
    admin_menu, users_menu, users_list_menu,
    user_card_menu, role_menu, find_user_menu,
    promo_menu, promo_list_menu, promo_card_menu,
    admin_shops_menu, admin_shop_card_menu,
)
