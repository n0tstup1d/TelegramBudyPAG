from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import SUPPORT_URL, PARTNERSHIP_URL, CONTENT_URL


def promo_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin:promo_create")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin:promo_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")]
    ])


def promo_list_menu(promos: list) -> InlineKeyboardMarkup:
    buttons = []
    for promo in promos:
        status = "✅" if promo.is_active else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {promo.code} — {promo.discount} ₽ ({promo.used_count}/{promo.usage_limit})",
                callback_data=f"admin:promo_card:{promo.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:promo")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def promo_card_menu(promo_id: int, is_active: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Выключить" if is_active else "✅ Включить",
            callback_data=f"admin:promo_toggle:{promo_id}"
        )],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:promo_delete:{promo_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:promo_list")]
    ])


def bottom_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Тех. поддержка")]
        ],
        resize_keyboard=True,
        persistent=True
    )


SECTIONS = {
    "supplements": "💊 Добавки",
    "sleep": "💤 Сон",
    "nutrition": "🥗 Питание",
    "brain": "🧠 Концентрация и мозг",
    "recovery": "🏃 Восстановление",
    "analytics": "📊 Анализы и мониторинг"
}


def terms_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Читать соглашение", url="https://telegra.ph/твоя-ссылка")],
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="terms:accept")],
        [InlineKeyboardButton(text="❌ Не принимаю", callback_data="terms:decline")],
        [InlineKeyboardButton(text="💬 Связаться с нами", url=SUPPORT_URL)]
    ])


def pay_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data="pay")],
        [InlineKeyboardButton(text="💬 Проблемы с оплатой?", url=SUPPORT_URL)]
    ])


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💤 Сон", callback_data="section:sleep")],
        [InlineKeyboardButton(text="🥗 Питание", callback_data="section:nutrition")],
        [InlineKeyboardButton(text="🧠 Концентрация и мозг", callback_data="section:brain")],
        [InlineKeyboardButton(text="💊 Добавки", callback_data="section:supplements")],
        [InlineKeyboardButton(text="🏃 Восстановление", callback_data="section:recovery")],
        [InlineKeyboardButton(text="📊 Анализы и мониторинг", callback_data="section:analytics")],
        [InlineKeyboardButton(text="🏪 Магазины БАДов", callback_data="section:shops")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="📢 Реклама и сотрудничество", url=PARTNERSHIP_URL)]
    ])


def banned_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Обратиться в поддержку", url=SUPPORT_URL)]
    ])


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Тех. поддержка", url=SUPPORT_URL)],
        [InlineKeyboardButton(text="❓ Вопрос по контенту", url=CONTENT_URL)],
        [InlineKeyboardButton(text="📢 Реклама и сотрудничество", url=PARTNERSHIP_URL)]
    ])

# ——— Контент ———

def section_menu(section_id: str, content: dict) -> InlineKeyboardMarkup:
    section = content.get(section_id, {})
    buttons = []
    for topic_id, topic in section.items():
        buttons.append([
            InlineKeyboardButton(
                text=topic.get("title", "Без названия"),
                callback_data=f"topic:{section_id}:{topic_id}:0"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def topic_menu(section_id: str, topic_id: str, chunk: int = 0, total_chunks: int = 1) -> InlineKeyboardMarkup:
    buttons = []

    if total_chunks > 1:
        nav = []
        if chunk > 0:
            nav.append(InlineKeyboardButton(text="⬅️ Часть", callback_data=f"topic:{section_id}:{topic_id}:{chunk - 1}"))
        if chunk < total_chunks - 1:
            nav.append(InlineKeyboardButton(text="Часть ➡️", callback_data=f"topic:{section_id}:{topic_id}:{chunk + 1}"))
        if nav:
            buttons.append(nav)

    buttons.extend([
        [InlineKeyboardButton(text="📖 Подробнее", callback_data=f"page:{section_id}:{topic_id}:0:0")],
        [InlineKeyboardButton(text="❓ Вопросы", callback_data=f"questions:{section_id}:{topic_id}:0")],
        [InlineKeyboardButton(text="🔬 Источники", callback_data=f"sources:{section_id}:{topic_id}:0")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"section:{section_id}")]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def pages_menu(
    section_id: str,
    topic_id: str,
    page: int,
    total: int,
    chunk: int = 0,
    total_chunks: int = 1
) -> InlineKeyboardMarkup:
    buttons = []

    if total_chunks > 1:
        chunk_nav = []
        if chunk > 0:
            chunk_nav.append(InlineKeyboardButton(text="⬅️ Часть", callback_data=f"page:{section_id}:{topic_id}:{page}:{chunk - 1}"))
        if chunk < total_chunks - 1:
            chunk_nav.append(InlineKeyboardButton(text="Часть ➡️", callback_data=f"page:{section_id}:{topic_id}:{page}:{chunk + 1}"))
        if chunk_nav:
            buttons.append(chunk_nav)

    page_nav = []
    if page > 0:
        page_nav.append(InlineKeyboardButton(text="⬅️ Страница", callback_data=f"page:{section_id}:{topic_id}:{page - 1}:0"))
    if page < total - 1:
        page_nav.append(InlineKeyboardButton(text="Страница ➡️", callback_data=f"page:{section_id}:{topic_id}:{page + 1}:0"))
    if page_nav:
        buttons.append(page_nav)

    buttons.append([InlineKeyboardButton(text="⬅️ К теме", callback_data=f"topic:{section_id}:{topic_id}:0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def questions_menu(section_id: str, topic_id: str, topic: dict, page: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    questions = topic.get("questions", [])
    total = len(questions)
    max_page = max(0, (total - 1) // page_size)
    page = max(0, min(page, max_page))
    start = page * page_size
    end = min(start + page_size, total)

    buttons = []
    for index in range(start, end):
        q = questions[index]
        buttons.append([
            InlineKeyboardButton(
                text=q.get("question", "Вопрос"),
                callback_data=f"question:{section_id}:{topic_id}:{index}:0"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"questions:{section_id}:{topic_id}:{page - 1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"questions:{section_id}:{topic_id}:{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="⬅️ К теме", callback_data=f"topic:{section_id}:{topic_id}:0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sources_menu(section_id: str, topic_id: str, chunk: int = 0, total_chunks: int = 1) -> InlineKeyboardMarkup:
    buttons = []

    if total_chunks > 1:
        nav = []
        if chunk > 0:
            nav.append(InlineKeyboardButton(text="⬅️ Часть", callback_data=f"sources:{section_id}:{topic_id}:{chunk - 1}"))
        if chunk < total_chunks - 1:
            nav.append(InlineKeyboardButton(text="Часть ➡️", callback_data=f"sources:{section_id}:{topic_id}:{chunk + 1}"))
        if nav:
            buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="⬅️ К теме", callback_data=f"topic:{section_id}:{topic_id}:0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def answer_menu(
    section_id: str,
    topic_id: str,
    question_index: int | None = None,
    chunk: int = 0,
    total_chunks: int = 1,
    questions_page_size: int = 10
) -> InlineKeyboardMarkup:
    buttons = []

    if question_index is not None and total_chunks > 1:
        nav = []
        if chunk > 0:
            nav.append(InlineKeyboardButton(text="⬅️ Часть", callback_data=f"question:{section_id}:{topic_id}:{question_index}:{chunk - 1}"))
        if chunk < total_chunks - 1:
            nav.append(InlineKeyboardButton(text="Часть ➡️", callback_data=f"question:{section_id}:{topic_id}:{question_index}:{chunk + 1}"))
        if nav:
            buttons.append(nav)

    questions_page = 0
    if question_index is not None:
        questions_page = max(0, question_index // questions_page_size)

    buttons.append([InlineKeyboardButton(text="⬅️ К вопросам", callback_data=f"questions:{section_id}:{topic_id}:{questions_page}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="admin:referral")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="👤 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin:promo")],
        [InlineKeyboardButton(text="🏪 Магазины", callback_data="admin:shops")],
        [InlineKeyboardButton(text="⚙️ Назначить роль", callback_data="admin:roles")],
    ])


def users_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin:users_list:all:0")],
        [InlineKeyboardButton(text="⚙️ Администраторы", callback_data="admin:users_list:admins:0")],
        [InlineKeyboardButton(text="🚫 Забаненные", callback_data="admin:users_list:banned:0")],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin:user_find")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")]
    ])


def users_list_menu(users: list, category: str, page: int, total: int) -> InlineKeyboardMarkup:
    buttons = []
    for user in users:
        username = f"@{user.username}" if user.username else user.full_name
        sub_icon = "💳" if user.has_subscription else "🆓"
        buttons.append([
            InlineKeyboardButton(
                text=f"{sub_icon} {username}",
                callback_data=f"admin:user_card:{user.user_id}"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin:users_list:{category}:{page-1}"))
    if (page + 1) * 10 < total:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin:users_list:{category}:{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:users")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_card_menu(user_id: int, has_subscription: bool, role: str) -> InlineKeyboardMarkup:
    buttons = []

    if has_subscription:
        buttons.append([InlineKeyboardButton(text="❌ Забрать подписку", callback_data=f"admin:sub_remove:{user_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="✅ Выдать подписку", callback_data=f"admin:sub_give:{user_id}")])

    buttons.append([InlineKeyboardButton(text="🎭 Изменить роль", callback_data=f"admin:role_change:{user_id}")])
    buttons.append([
        InlineKeyboardButton(
            text="🚫 Забанить" if role != "banned" else "✅ Разбанить",
            callback_data=f"admin:ban:{user_id}" if role != "banned" else f"admin:unban:{user_id}"
        )
    ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:users")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def role_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Пользователь", callback_data=f"admin:set_role:{user_id}:user")],
        [InlineKeyboardButton(text="🛡 Модератор", callback_data=f"admin:set_role:{user_id}:moderator")],
        [InlineKeyboardButton(text="⚙️ Администратор", callback_data=f"admin:set_role:{user_id}:admin")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:users")]
    ])


def find_user_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Искать снова", callback_data="admin:user_find")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:users")]
    ])


def shops_menu(shops: list) -> InlineKeyboardMarkup:
    buttons = []
    for shop in shops:
        buttons.append([
            InlineKeyboardButton(
                text=f"🏪 {shop.name}",
                callback_data=f"shop:{shop.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shop_card_menu(shop_id: int, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Перейти в магазин", callback_data=f"shop_click:{shop_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="section:shops")]
    ])


def admin_shops_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить магазин", callback_data="admin:shop_add")],
        [InlineKeyboardButton(text="📋 Список магазинов", callback_data="admin:shop_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")]
    ])


def admin_shop_card_menu(shop_id: int, is_active: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ Выключить" if is_active else "✅ Включить",
            callback_data=f"admin:shop_toggle:{shop_id}"
        )],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:shop_delete:{shop_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:shop_list")]
    ])
