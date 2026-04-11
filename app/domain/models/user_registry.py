from datetime import time

from sqlalchemy import Boolean, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class UserNotificationSettings(SchemaTableMixin, BaseModel):
    __tablename__ = "user_notification_settings"
    __schema_name__ = "user_registry"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    reminders_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    preferred_reminder_time_local: Mapped[time | None] = mapped_column(
        Time(), nullable=True
    )
    timezone_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
