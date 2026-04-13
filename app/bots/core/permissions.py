from __future__ import annotations

from collections.abc import Iterable


def is_admin_user(user_id: int | None, admin_ids: Iterable[int] | None = None) -> bool:
    if user_id is None or admin_ids is None:
        return False
    return user_id in set(admin_ids)


def can_view_debug(
    user_id: int | None,
    *,
    admin_ids: Iterable[int] | None = None,
    debug_enabled: bool = False,
) -> bool:
    return debug_enabled and is_admin_user(user_id, admin_ids)


def has_role(required_role: str, user_roles: Iterable[str] | None) -> bool:
    if not required_role or user_roles is None:
        return False
    return required_role in set(user_roles)
