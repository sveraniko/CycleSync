"""Reusable Telegram bot UI foundation helpers."""

from app.bots.core.flow import (
    CONTAINER_MESSAGE_ID_KEY,
    delete_user_input_message,
    get_container_message_id,
    remember_container,
    reset_container,
    safe_edit_or_send,
    send_or_edit,
)
from app.bots.core.formatting import (
    compact_status_label,
    escape_html_text,
    format_decimal_human,
    mask_human_id,
)
from app.bots.core.permissions import (
    can_view_debug,
    has_role,
    is_admin_user,
)

__all__ = [
    "CONTAINER_MESSAGE_ID_KEY",
    "send_or_edit",
    "safe_edit_or_send",
    "remember_container",
    "get_container_message_id",
    "reset_container",
    "delete_user_input_message",
    "format_decimal_human",
    "compact_status_label",
    "mask_human_id",
    "escape_html_text",
    "is_admin_user",
    "can_view_debug",
    "has_role",
]
