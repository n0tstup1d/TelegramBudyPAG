from __future__ import annotations

from services.permissions import is_staff_role


def has_access(user) -> bool:
    """Единое правило доступа к закрытому контенту без зависимостей от Telegram."""
    if not user:
        return False
    if is_staff_role(getattr(user, "role", None)):
        return True
    return bool(getattr(user, "has_subscription", False))
