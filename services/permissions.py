from __future__ import annotations

STAFF_ROLES = frozenset({"admin", "moderator"})


def is_staff_role(role: str | None) -> bool:
    return role in STAFF_ROLES


def is_superadmin_role(role: str | None) -> bool:
    return role == "admin"
