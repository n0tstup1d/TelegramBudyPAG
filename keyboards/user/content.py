from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def section_menu(section_id: str, content: dict) -> InlineKeyboardMarkup:
    section = content.get(section_id, {})
    buttons = []
    for topic_id, topic in section.items():
        buttons.append([
            InlineKeyboardButton(
                text=topic.get("title", topic_id),
                callback_data=f"topic:{section_id}:{topic_id}:0",
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back:main")])
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
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"section:{section_id}")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def pages_menu(
    section_id: str,
    topic_id: str,
    page: int,
    total: int,
    chunk: int = 0,
    total_chunks: int = 1,
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
                callback_data=f"question:{section_id}:{topic_id}:{index}:0",
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
    questions_page_size: int = 10,
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
