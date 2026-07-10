from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


NOOP = "noop"


def section_menu(section_id: str, content: dict) -> InlineKeyboardMarkup:
    section = content.get(section_id, {})
    buttons = []
    for topic_id, topic in section.items():
        buttons.append([
            InlineKeyboardButton(
                text=topic.get("title", topic_id),
                callback_data=f"topic:{section_id}:{topic_id}:0"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🏠 В меню", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def topic_menu(section_id: str, topic_id: str, chunk: int = 0, total_chunks: int = 1) -> InlineKeyboardMarkup:
    buttons = []

    if total_chunks > 1:
        nav = []
        if chunk > 0:
            nav.append(InlineKeyboardButton(text="⬅️ Часть", callback_data=f"topic:{section_id}:{topic_id}:{chunk - 1}"))
        nav.append(InlineKeyboardButton(text=f"{chunk + 1}/{total_chunks}", callback_data=NOOP))
        if chunk < total_chunks - 1:
            nav.append(InlineKeyboardButton(text="Часть ➡️", callback_data=f"topic:{section_id}:{topic_id}:{chunk + 1}"))
        buttons.append(nav)

    buttons.extend([
        [InlineKeyboardButton(text="📖 Читать тему", callback_data=f"page:{section_id}:{topic_id}:0:0")],
        [InlineKeyboardButton(text="❓ Вопросы и ответы", callback_data=f"questions:{section_id}:{topic_id}:0")],
        [InlineKeyboardButton(text="🔬 Источники", callback_data=f"sources:{section_id}:{topic_id}:0")],
        [InlineKeyboardButton(text="⬅️ К разделу", callback_data=f"section:{section_id}")],
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
        chunk_nav.append(InlineKeyboardButton(text=f"{chunk + 1}/{total_chunks}", callback_data=NOOP))
        if chunk < total_chunks - 1:
            chunk_nav.append(InlineKeyboardButton(text="Часть ➡️", callback_data=f"page:{section_id}:{topic_id}:{page}:{chunk + 1}"))
        buttons.append(chunk_nav)

    # Навигация по страницам всегда в 3 кнопки:
    # ⬅️ | текущая/всего | ➡️
    # На первой/последней странице крайняя кнопка остаётся видимой,
    # но становится декоративной, чтобы сетка не прыгала.
    prev_callback = f"page:{section_id}:{topic_id}:{page - 1}:0" if page > 0 else NOOP
    next_callback = f"page:{section_id}:{topic_id}:{page + 1}:0" if page < total - 1 else NOOP
    buttons.append([
        InlineKeyboardButton(text="⬅️", callback_data=prev_callback),
        InlineKeyboardButton(text=f"{page + 1}/{total}", callback_data=NOOP),
        InlineKeyboardButton(text="➡️", callback_data=next_callback),
    ])

    buttons.append([InlineKeyboardButton(text="⬅️ К теме", callback_data=f"topic:{section_id}:{topic_id}:0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def questions_menu(section_id: str, topic_id: str, topic: dict, page: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    questions = topic.get("questions", [])
    total = len(questions)
    max_page = max((total - 1) // page_size, 0)
    page = max(0, min(page, max_page))

    start = page * page_size
    end = start + page_size
    buttons = []

    for i, q in enumerate(questions[start:end], start=start):
        buttons.append([
            InlineKeyboardButton(
                text=q.get("question", f"Вопрос {i + 1}"),
                callback_data=f"question:{section_id}:{topic_id}:{i}:0"
            )
        ])

    if total > page_size:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"questions:{section_id}:{topic_id}:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{max_page + 1}", callback_data=NOOP))
        if page < max_page:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"questions:{section_id}:{topic_id}:{page + 1}"))
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="⬅️ К теме", callback_data=f"topic:{section_id}:{topic_id}:0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sources_menu(section_id: str, topic_id: str, chunk: int = 0, total_chunks: int = 1) -> InlineKeyboardMarkup:
    buttons = []
    if total_chunks > 1:
        nav = []
        if chunk > 0:
            nav.append(InlineKeyboardButton(text="⬅️ Часть", callback_data=f"sources:{section_id}:{topic_id}:{chunk - 1}"))
        nav.append(InlineKeyboardButton(text=f"{chunk + 1}/{total_chunks}", callback_data=NOOP))
        if chunk < total_chunks - 1:
            nav.append(InlineKeyboardButton(text="Часть ➡️", callback_data=f"sources:{section_id}:{topic_id}:{chunk + 1}"))
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="⬅️ К теме", callback_data=f"topic:{section_id}:{topic_id}:0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def answer_menu(
    section_id: str,
    topic_id: str,
    question_index: int,
    chunk: int = 0,
    total_chunks: int = 1,
    questions_page_size: int = 10,
) -> InlineKeyboardMarkup:
    buttons = []

    if total_chunks > 1:
        nav = []
        if chunk > 0:
            nav.append(InlineKeyboardButton(text="⬅️ Часть", callback_data=f"question:{section_id}:{topic_id}:{question_index}:{chunk - 1}"))
        nav.append(InlineKeyboardButton(text=f"{chunk + 1}/{total_chunks}", callback_data=NOOP))
        if chunk < total_chunks - 1:
            nav.append(InlineKeyboardButton(text="Часть ➡️", callback_data=f"question:{section_id}:{topic_id}:{question_index}:{chunk + 1}"))
        buttons.append(nav)

    questions_page = question_index // questions_page_size
    buttons.append([InlineKeyboardButton(text="⬅️ К вопросам", callback_data=f"questions:{section_id}:{topic_id}:{questions_page}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
