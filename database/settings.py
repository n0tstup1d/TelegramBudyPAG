from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Setting


def parse_bool_setting(value: str | None, *, default: bool = False) -> bool:
    """Преобразует строковое значение настройки в bool.

    Неизвестное или отсутствующее значение возвращает безопасный default.
    Для пользовательских функций безопасный default — выключено.
    """
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on", "да", "вкл"}:
        return True
    if normalized in {"0", "false", "no", "off", "нет", "выкл"}:
        return False
    return default


async def get_setting(session: AsyncSession, key: str) -> str | None:
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        session.add(Setting(key=key, value=value))
    await session.commit()


async def apply_security_defaults(session: AsyncSession) -> bool:
    """Один раз отключает рискованные функции после установки обновления.

    Возвращает True, если настройки были изменены. После установки маркера
    администратор может снова включать функции через панель — повторного сброса не будет.
    """
    marker_key = "security_defaults_v1_applied"
    if parse_bool_setting(await get_setting(session, marker_key), default=False):
        return False

    for key in ("referral_enabled", "shops_enabled"):
        result = await session.execute(select(Setting).where(Setting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = "false"
        else:
            session.add(Setting(key=key, value="false"))

    marker_result = await session.execute(select(Setting).where(Setting.key == marker_key))
    marker = marker_result.scalar_one_or_none()
    if marker:
        marker.value = "true"
    else:
        session.add(Setting(key=marker_key, value="true"))
    await session.commit()
    return True


async def is_referral_enabled(session: AsyncSession) -> bool:
    # Без явного включения администратором реферальная система скрыта.
    return parse_bool_setting(await get_setting(session, "referral_enabled"), default=False)


async def is_shops_enabled(session: AsyncSession) -> bool:
    # Без явного включения администратором раздел магазинов скрыт.
    return parse_bool_setting(await get_setting(session, "shops_enabled"), default=False)


async def get_referral_reward(session: AsyncSession) -> int:
    value = await get_setting(session, "referral_reward")
    try:
        return max(0, int(value)) if value is not None else 200
    except (TypeError, ValueError):
        return 200


async def get_min_withdrawal(session: AsyncSession) -> int:
    value = await get_setting(session, "min_withdrawal")
    try:
        return max(1, int(value)) if value is not None else 200
    except (TypeError, ValueError):
        return 200
