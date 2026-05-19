"""
ORM-модель аудита генерации параметров (таблица param_generation_audit).

Записывает каждую неудачную попытку генерации параметров задания
с указанием номера попытки и причины отклонения.
"""

import uuid

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.core.database import Base
from backend.app.models.mixins import utc_now


class ParamGenerationAudit(Base):
    """Аудит неуспешных попыток генерации параметров."""

    __tablename__ = "param_generation_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    attempt_number = Column(Integer, nullable=False)

    rejection_reason = Column(Text, nullable=False)

    created_at = Column(
        DateTime,
        default=utc_now,
        nullable=False,
    )

    task = relationship("Task", back_populates="param_audits")

    def __repr__(self) -> str:
        return (
            f"<ParamGenerationAudit task_id={self.task_id} "
            f"attempt={self.attempt_number}>"
        )
