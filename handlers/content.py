import json
import os
from aiogram import Router, F
from aiogram.types import CallbackQuery
from keyboards.menus import (
    section_menu, topic_menu, pages_menu,
    questions_menu, sources_menu, answer_menu,
    SECTIONS
)

router = Router()

# Telegram ограничивает текст сообщения примерно 4096 символами.
# Берём запас, чтобы кнопки/служебная строка "Часть X/Y" не ломали отправку.
MAX_TEXT_LENGTH = 3700
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


def load_content() -> dict:
    raw_content = {}
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    if not os.path.exists(data_dir):
        return raw_content

    for entry in sorted(os.listdir(data_dir)):
        entry_path = os.path.join(data_dir, entry)

        if os.path.isdir(entry_path):
            # раздел разложен по файлам: data/supplements/*.json
            section_id = entry
            section_content = {}
            for file in sorted(os.listdir(entry_path)):
                if file.endswith(".json"):
                    with open(os.path.join(entry_path, file), encoding="utf-8") as f:
                        section_content.update(json.load(f))
            raw_content[section_id] = section_content

        elif entry.endswith(".json"):
            # раздел одним файлом: data/nutrition.json
            section_id = entry.replace(".json", "")
            if section_id in raw_content:
                continue  # папка уже загружена — не затираем её плоским файлом
            with open(entry_path, encoding="utf-8") as f:
                raw_content[section_id] = json.load(f)

    return make_safe_content(raw_content)


def make_safe_content(raw_content: dict) -> dict:
    """
    Делает короткие внутренние id тем: t0, t1, t2...
    Это нужно, потому что Telegram callback_data имеет лимит 64 байта.
    Сам JSON и его контент не меняются: оригинальный id остаётся внутри topic["id"].
    """
    safe_content = {}

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


@router.callback_query(F.data.startswith("section:"))
async def show_section(callback: CallbackQuery):
    section_id = callback.data.split(":")[1]
    title = SECTIONS.get(section_id, "Раздел")

    if section_id not in CONTENT or not CONTENT[section_id]:
        await callback.answer("Раздел пока пуст", show_alert=True)
        return

    await callback.message.edit_text(
        f"{title}\n\nВыбери тему:",
        reply_markup=section_menu(section_id, CONTENT)
    )
    await callback.answer()


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
    await callback.message.edit_text(
        text,
        reply_markup=topic_menu(section_id, topic_id, chunk, total_chunks)
    )
    await callback.answer()


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

    await callback.message.edit_text(
        text,
        reply_markup=pages_menu(section_id, topic_id, page, len(pages), chunk, total_chunks)
    )
    await callback.answer()


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

    await callback.message.edit_text(
        "❓ Выбери вопрос:",
        reply_markup=questions_menu(section_id, topic_id, topic, page=page, page_size=QUESTIONS_PAGE_SIZE)
    )
    await callback.answer()


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

    await callback.message.edit_text(
        text,
        reply_markup=answer_menu(section_id, topic_id, question_index, chunk, total_chunks, QUESTIONS_PAGE_SIZE)
    )
    await callback.answer()


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

    await callback.message.edit_text(
        text,
        reply_markup=sources_menu(section_id, topic_id, chunk, total_chunks)
    )
    await callback.answer()
