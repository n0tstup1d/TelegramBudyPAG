import random
import string
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User


def generate_referral_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    try:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        return result.scalar_one_or_none()
    except Exception:
        await session.rollback()
        raise


async def create_user(
    session: AsyncSession,
    user_id: int,
    username: str | None,
    full_name: str,
    referred_by: int | None = None
) -> User:
    try:
        referral_code = generate_referral_code()
        user = User(
            user_id=user_id,
            username=username,
            full_name=full_name,
            referral_code=referral_code,
            referred_by=referred_by
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    except Exception:
        await session.rollback()
        raise


async def agree_to_terms(session: AsyncSession, user_id: int) -> None:
    try:
        result = await session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.agreed_to_terms = True
            user.agreed_at = datetime.now()
            await session.commit()
    except Exception:
        await session.rollback()
        raise