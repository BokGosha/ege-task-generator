"""Переиспользуемые миксины для ORM-моделей."""

from datetime import datetime, UTC

from sqlalchemy import Column, DateTime


def utc_now() -> datetime:
    """Текущее время в UTC без tzinfo — для совместимости с naive DateTime-колонками."""
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    """Миксин для автоматического добавления временных меток."""

    created_at = Column(
        DateTime,
        default=utc_now,
        nullable=False,
        index=True,
        comment="Дата создания записи"
    )

    updated_at = Column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        comment="Дата последнего обновления"
    )
