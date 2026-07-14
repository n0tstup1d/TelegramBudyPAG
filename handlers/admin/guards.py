from database.crud import get_user
from database.engine import async_session
from services.permissions import is_staff_role, is_superadmin_role


async def is_admin(user_id: int) -> bool:
    async with async_session() as session:
        user = await get_user(session, user_id)
        return bool(user and is_staff_role(user.role))


async def is_superadmin(user_id: int) -> bool:
    async with async_session() as session:
        user = await get_user(session, user_id)
        return bool(user and is_superadmin_role(user.role))
