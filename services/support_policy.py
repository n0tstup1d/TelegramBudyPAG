from __future__ import annotations

from typing import Any

from config import SUPPORT_MAX_FILE_MB, SUPPORT_MAX_TEXT_LENGTH

CONTENT_SUPPORT_NOTICE = (
    "Мы можем пояснить материалы VEGA только в общем информационном виде. "
    "Не присылай результаты анализов, медицинские документы, диагнозы, сведения о лекарствах, "
    "подробности о здоровье или поведении ребёнка. Мы не ставим диагнозы, не подбираем дозировки, "
    "не отменяем лечение и не даём персональных медицинских или психологических назначений. "
    "По личной ситуации необходимо обратиться к профильному специалисту."
)

STAFF_SAFE_REPLY_TEMPLATE = (
    "Мы можем пояснить содержание материала в общем виде, но не анализируем индивидуальные симптомы, "
    "результаты обследований, диагнозы и лекарственные схемы. Мы также не ставим психологические или "
    "психиатрические диагнозы и не оцениваем поведение ребёнка по переписке. "
    "По личной ситуации необходимо обратиться к врачу, психологу, педагогу или другому профильному специалисту."
)

STAFF_CONTENT_WARNING = (
    "⚠️ Границы ответа: не ставить диагнозы; не разбирать анализы и симптомы; не назначать дозировки, "
    "лекарства или отмену лечения; не обещать исправить поведение ребёнка; не рекомендовать наказания; "
    "не запрашивать медицинские документы и специальные категории персональных данных. "
    "Разрешено только общее пояснение опубликованного материала."
)


def _largest_photo_size(message: Any) -> int | None:
    photos = getattr(message, "photo", None) or []
    sizes = [getattr(item, "file_size", None) for item in photos]
    known = [size for size in sizes if isinstance(size, int)]
    return max(known) if known else None


def validate_support_message(message: Any, category: str) -> tuple[bool, str | None]:
    """Проверяет формат обращения до копирования в рабочую группу.

    Вопросы по контенту принимаются только текстом, чтобы не собирать анализы,
    медицинские документы и изображения детей. Для технической поддержки
    разрешены текст и один скриншот/фотография разумного размера.
    """
    text = getattr(message, "text", None)
    if text is not None:
        if not text.strip():
            return False, "Сообщение пустое. Опиши вопрос текстом."
        if len(text) > SUPPORT_MAX_TEXT_LENGTH:
            return False, f"Сообщение слишком длинное. Максимум — {SUPPORT_MAX_TEXT_LENGTH} символов."
        return True, None

    if category == "content":
        return False, (
            "Для вопросов по контенту принимается только текст. Не присылай анализы, медицинские документы, "
            "фотографии, голосовые сообщения или сведения о здоровье и поведении детей."
        )

    photo = getattr(message, "photo", None)
    if photo:
        file_size = _largest_photo_size(message)
        max_bytes = SUPPORT_MAX_FILE_MB * 1024 * 1024
        if file_size is not None and file_size > max_bytes:
            return False, f"Скриншот слишком большой. Максимальный размер — {SUPPORT_MAX_FILE_MB} МБ."
        caption = getattr(message, "caption", None)
        if caption and len(caption) > SUPPORT_MAX_TEXT_LENGTH:
            return False, f"Подпись слишком длинная. Максимум — {SUPPORT_MAX_TEXT_LENGTH} символов."
        return True, None

    return False, (
        "Поддержка принимает текст и, для технического вопроса, один скриншот. "
        "Документы, видео, аудио, голосовые сообщения, контакты и геолокация не принимаются."
    )
