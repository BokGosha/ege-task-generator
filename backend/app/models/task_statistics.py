"""
ORM-модель статистики заданий (таблица task_statistics).

Статистика вычисляется динамически; таблица - placeholder для будущей
материализации агрегатов.
"""

import uuid

from sqlalchemy import Column, Integer, String, Index
from sqlalchemy.dialects.postgresql import UUID

from backend.app.core.database import Base
from backend.app.models.mixins import TimestampMixin


class TaskStatistics(Base, TimestampMixin):
    """
    Конституционная доменная сущность для статистики.
    В MVP статистика вычисляется динамически из базовых таблиц —
    эта таблица сохраняется как placeholder-схема.
    """

    __tablename__ = "task_statistics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_type = Column(Integer, nullable=False, index=True)

    subtype = Column(String(64), nullable=True, index=True)

    status = Column(String(20), nullable=True)

    quality_verdict = Column(String(20), nullable=True)

    __table_args__ = (
        Index("ix_statistics_type_subtype", "task_type", "subtype"),
    )

    def __repr__(self) -> str:
        return (
            f"<TaskStatistics type={self.task_type} subtype={self.subtype}>"
        )
