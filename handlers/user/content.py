import json
import os
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from keyboards.user.content import (
    section_menu, topic_menu, pages_menu,
    questions_menu, sources_menu, answer_menu,
)
from keyboards.user.main import SECTIONS
from services.content_protection import (
    check_and_record_content_access,
    format_retry_after,
    protect_text,
)

router = Router()

# Telegram ограничивает текст сообщения примерно 4096 символами.
# Берём запас, чтобы кнопки/служебная строка "Часть X/Y" не ломали отправку.
MAX_TEXT_LENGTH = 3300
QUESTIONS_PAGE_SIZE = 10


def split_long_text(text: str, max_len: int = MAX_TEXT_LENGTH) -> list[str]:
    """Делит длинный текст на части, не вырезая содержимое."""
    text = str(text or "")
    if len(text) <= max_len:
        return [text]

    chunks = []
    rest = text

    while len(rest) > max_len:
        cut = rest.rfind("\n\n", 0, max_len)
        if cut < max_len // 2:
            cut = rest.rfind("\n", 0, max_len)
        if cut < max_len // 2:
            cut = rest.rfind(" ", 0, max_len)
        if cut <= 0:
            cut = max_len

        chunks.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()

    if rest:
        chunks.append(rest)

    return chunks or [""]


def get_text_chunk(text: str, chunk_index: int = 0) -> tuple[str, int, int]:
    chunks = split_long_text(text)
    total = len(chunks)
    chunk_index = max(0, min(chunk_index, total - 1))

    visible_text = chunks[chunk_index]
    if total > 1:
        visible_text = f"Часть {chunk_index + 1}/{total}\n\n{visible_text}"

    return visible_text, chunk_index, total


SECTION_ALIASES = {
    "supplements": "supplements",
    "Supplements": "supplements",
    "sleep": "sleep",
    "Sleep": "sleep",
    "nutrition": "nutrition",
    "Nutrition": "nutrition",
    "brain": "brain",
    "focus_brain": "brain",
    "Focus_and_Brain": "brain",
    "focus_and_brain": "brain",
    "recovery": "recovery",
    "Recovery": "recovery",
    "analytics": "analytics",
    "tests_monitoring": "analytics",
    "Tests_and_Monitoring": "analytics",
    "tests_and_monitoring": "analytics",
}


def normalize_section_id(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value).strip()
    if value in SECTION_ALIASES:
        return SECTION_ALIASES[value]
    lowered = value.lower().replace(" ", "_").replace("-", "_")
    return SECTION_ALIASES.get(lowered, lowered)


def is_topic_dict(value: dict) -> bool:
    """Проверяет, похож ли dict на одну тему контента."""
    if not isinstance(value, dict):
        return False
    required_any = {"title", "short", "pages", "questions", "sources"}
    return bool(required_any.intersection(value.keys()))


def merge_topic_payload(raw_content: dict, preferred_section_id: str | None, payload: dict) -> None:
    """
    Поддерживает все варианты раскладки data:
    1) data/sleep/*.json
    2) data/Sleep/*.json
    3) data/nutrition.json
    4) общий JSON в корне data со всеми темами

    Контент внутри JSON не меняется, меняется только то, в какой раздел он попадает.
    """
    if not isinstance(payload, dict):
        return

    normalized_preferred = normalize_section_id(preferred_section_id)

    # Вариант: файл содержит прямой раздел: {"sleep": { ...topics... }}
    section_like_keys = [key for key in payload.keys() if normalize_section_id(key) in SECTION_ALIASES.values()]
    if section_like_keys and not all(is_topic_dict(v) for v in payload.values() if isinstance(v, dict)):
        for key, value in payload.items():
            section_id = normalize_section_id(key)
            if section_id and isinstance(value, dict):
                raw_content.setdefault(section_id, {}).update(value)
        return

    # Вариант: файл содержит темы: {"vitamin_d": {"category": "supplements", ...}}
    if all(is_topic_dict(v) for v in payload.values() if isinstance(v, dict)):
        for topic_id, topic in payload.items():
            if not isinstance(topic, dict):
                continue
            section_id = normalize_section_id(topic.get("category")) or normalized_preferred
            if not section_id:
                continue
            raw_content.setdefault(section_id, {})[topic_id] = topic
        return

    # Вариант: файл/папка уже является разделом, а payload — набор тем без category.
    if normalized_preferred:
        raw_content.setdefault(normalized_preferred, {}).update(payload)


def load_content() -> dict:
    raw_content = {}
    # handlers/user/content.py -> project root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(base_dir, "data")
    if not os.path.exists(data_dir):
        return raw_content

    for entry in sorted(os.listdir(data_dir)):
        entry_path = os.path.join(data_dir, entry)

        if os.path.isdir(entry_path):
            # Поддерживаем и lowercase-папки, и английские папки из архива:
            # data/sleep/*.json, data/Sleep/*.json, data/Focus_and_Brain/*.json и т.д.
            section_id = normalize_section_id(entry)
            for file in sorted(os.listdir(entry_path)):
                if not file.endswith(".json"):
                    continue
                with open(os.path.join(entry_path, file), encoding="utf-8") as f:
                    merge_topic_payload(raw_content, section_id, json.load(f))

        elif entry.endswith(".json"):
            # Поддерживаем как data/sleep.json, так и общий data/fitness_app_content_all.json.
            section_id = normalize_section_id(entry.replace(".json", ""))
            with open(entry_path, encoding="utf-8") as f:
                merge_topic_payload(raw_content, section_id, json.load(f))

    return make_safe_content(raw_content)


def make_safe_content(raw_content: dict) -> dict:
    """
    Делает короткие внутренние id тем: t0, t1, t2...
    Это нужно, потому что Telegram callback_data имеет лимит 64 байта.
    Сам JSON и его контент не меняются: оригинальный id остаётся внутри topic["id"].
    """
    safe_content = {}

    # Гарантируем наличие всех пользовательских разделов, чтобы меню не падало.
    for section_id in ("supplements", "sleep", "nutrition", "brain", "recovery", "analytics"):
        raw_content.setdefault(section_id, {})

    for section_id, section in raw_content.items():
        if not isinstance(section, dict):
            safe_content[section_id] = section
            continue

        safe_section = {}
        for index, (original_topic_id, topic) in enumerate(section.items()):
            safe_topic_id = f"t{index}"
            if isinstance(topic, dict):
                topic.setdefault("_original_topic_id", original_topic_id)
            safe_section[safe_topic_id] = topic

        safe_content[section_id] = safe_section

    return safe_content

CONTENT = load_content()


async def _render_paid_content(
    callback: CallbackQuery,
    text: str,
    reply_markup,
    *,
    content_id: str,
) -> bool:
    """Показывает платный материал в защищённом сообщении с персональной меткой."""
    result = await check_and_record_content_access(
        callback.message.bot,
        callback.from_user,
        content_id,
    )
    if not result.allowed:
        await callback.answer(
            "🛡 Защитная пауза: материалы открывались слишком быстро. "
            f"Попробуйте снова через {format_retry_after(result.retry_after)}",
            show_alert=True,
        )
        return False

    protected_text = protect_text(text, callback.from_user.id)
    message = callback.message

    if getattr(message, "has_protected_content", False):
        try:
            await message.edit_text(protected_text, reply_markup=reply_markup)
            await callback.answer()
            return True
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                await callback.answer()
                return True
            # Редко Telegram запрещает редактирование старого сообщения. Ниже отправим новое.

    await message.answer(
        protected_text,
        reply_markup=reply_markup,
        protect_content=True,
    )
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    await callback.answer()
    return True


def _topic_log_id(section_id: str, topic_id: str, topic: dict) -> str:
    original_id = topic.get("_original_topic_id", topic_id) if isinstance(topic, dict) else topic_id
    return f"{section_id}:{original_id}"


@router.callback_query(F.data.startswith("section:"))
async def show_section(callback: CallbackQuery):
    section_id = callback.data.split(":")[1]
    title = SECTIONS.get(section_id, "Раздел")

    if section_id not in CONTENT or not CONTENT[section_id]:
        await callback.answer("Раздел пока пуст", show_alert=True)
        return

    await _render_paid_content(
        callback,
        f"{title}\n\nВыбери тему:",
        section_menu(section_id, CONTENT),
        content_id=f"section:{section_id}",
    )


@router.callback_query(F.data.startswith("topic:"))
async def show_topic(callback: CallbackQuery):
    parts = callback.data.split(":")
    section_id = parts[1]
    topic_id = parts[2]
    chunk = int(parts[3]) if len(parts) > 3 else 0

    topic = CONTENT.get(section_id, {}).get(topic_id)
    if not topic:
        await callback.answer("Тема не найдена", show_alert=True)
        return

    text, chunk, total_chunks = get_text_chunk(topic.get("short", ""), chunk)
    await _render_paid_content(
        callback,
        text,
        topic_menu(section_id, topic_id, chunk, total_chunks),
        content_id=f"topic:{_topic_log_id(section_id, topic_id, topic)}:chunk:{chunk}",
    )


@router.callback_query(F.data.startswith("page:"))
async def show_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    section_id = parts[1]
    topic_id = parts[2]
    page = int(parts[3])
    chunk = int(parts[4]) if len(parts) > 4 else 0

    topic = CONTENT.get(section_id, {}).get(topic_id)
    if not topic:
        await callback.answer("Тема не найдена", show_alert=True)
        return

    pages = topic.get("pages", [])
    if not pages:
        await callback.answer("Страниц пока нет", show_alert=True)
        return

    page = max(0, min(page, len(pages) - 1))
    text, chunk, total_chunks = get_text_chunk(pages[page], chunk)

    await _render_paid_content(
        callback,
        text,
        pages_menu(section_id, topic_id, page, len(pages), chunk, total_chunks),
        content_id=f"page:{_topic_log_id(section_id, topic_id, topic)}:{page}:chunk:{chunk}",
    )


@router.callback_query(F.data.startswith("questions:"))
async def show_questions(callback: CallbackQuery):
    parts = callback.data.split(":")
    section_id = parts[1]
    topic_id = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0

    topic = CONTENT.get(section_id, {}).get(topic_id)
    if not topic or not topic.get("questions"):
        await callback.answer("Вопросов пока нет", show_alert=True)
        return

    await _render_paid_content(
        callback,
        "❓ Выбери вопрос:",
        questions_menu(section_id, topic_id, topic, page=page, page_size=QUESTIONS_PAGE_SIZE),
        content_id=f"questions:{_topic_log_id(section_id, topic_id, topic)}:list:{page}",
    )


@router.callback_query(F.data.startswith("question:"))
async def show_answer(callback: CallbackQuery):
    parts = callback.data.split(":")
    section_id = parts[1]
    topic_id = parts[2]
    question_index = int(parts[3])
    chunk = int(parts[4]) if len(parts) > 4 else 0

    topic = CONTENT.get(section_id, {}).get(topic_id)
    if not topic:
        await callback.answer("Не найдено", show_alert=True)
        return

    questions = topic.get("questions", [])
    if question_index < 0 or question_index >= len(questions):
        await callback.answer("Вопрос не найден", show_alert=True)
        return

    question = questions[question_index]
    full_text = f"{question.get('question', '')}\n\n{question.get('answer', '')}"
    text, chunk, total_chunks = get_text_chunk(full_text, chunk)

    await _render_paid_content(
        callback,
        text,
        answer_menu(section_id, topic_id, question_index, chunk, total_chunks, QUESTIONS_PAGE_SIZE),
        content_id=(
            f"question:{_topic_log_id(section_id, topic_id, topic)}:"
            f"{question_index}:chunk:{chunk}"
        ),
    )


@router.callback_query(F.data.startswith("sources:"))
async def show_sources(callback: CallbackQuery):
    parts = callback.data.split(":")
    section_id = parts[1]
    topic_id = parts[2]
    chunk = int(parts[3]) if len(parts) > 3 else 0

    topic = CONTENT.get(section_id, {}).get(topic_id)
    if not topic:
        await callback.answer("Не найдено", show_alert=True)
        return

    sources = topic.get("sources", [])
    if not sources:
        await callback.answer("Источники не указаны", show_alert=True)
        return

    lines = []
    for i, src in enumerate(sources):
        if isinstance(src, dict):
            title = src.get("title") or src.get("url") or f"Источник {i + 1}"
            url = src.get("url", "")
            level = src.get("level")
            line = f"{i + 1}. {title}"
            if level:
                line += f"\nУровень: {level}"
            if url:
                line += f"\n{url}"
            lines.append(line)
        else:
            lines.append(f"{i + 1}. {src}")

    full_text = "🔬 Источники:\n\n" + "\n\n".join(lines)
    text, chunk, total_chunks = get_text_chunk(full_text, chunk)

    await _render_paid_content(
        callback,
        text,
        sources_menu(section_id, topic_id, chunk, total_chunks),
        content_id=f"sources:{_topic_log_id(section_id, topic_id, topic)}:chunk:{chunk}",
    )
