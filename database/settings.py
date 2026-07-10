from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Setting


async def get_setting(session: AsyncSession, key: str) -> str | None:
    result = await session.execute(
        select(Setting).where(Setting.key == key)
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(
        select(Setting).where(Setting.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        session.add(Setting(key=key, value=value))
    await session.commit()


async def is_referral_enabled(session: AsyncSession) -> bool:
    value = await get_setting(session, "referral_enabled")
    # По умолчанию реферальная система включена.
    # Если админ явно выключил её через админку, в БД будет "false".
    return value != "false"


async def get_referral_reward(session: AsyncSession) -> int:
    value = await get_setting(session, "referral_reward")
    return int(value) if value else 200


async def get_min_withdrawal(session: AsyncSession) -> int:
    value = await get_setting(session, "min_withdrawal")
    return int(value) if value else 200