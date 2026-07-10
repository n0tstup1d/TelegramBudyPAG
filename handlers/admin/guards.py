from database.crud import get_user
from database.engine import async_session


async def is_admin(user_id: int) -> bool:
    async with async_session() as session:
        user = await get_user(session, user_id)
        return bool(user and user.role in ("admin", "moderator"))


async def is_superadmin(user_id: int) -> bool:
    async with async_session() as session:
        user = await get_user(session, user_id)
        return bool(user and user.role == "admin")
