"""
ORM-модель профиля качества (таблица task_quality).

Хранит результаты проверки формулировки по 5 булевым критериям
и связанные причины отклонения.
"""

import uuid

from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Index, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.core.database import Base
from backend.app.models.mixins import utc_now


class TaskQuality(Base):
    """
    Профиль качества формулировки для конкретной итерации.
    5 булевых критериев с текстовыми пояснениями при fail.
    """

    __tablename__ = "task_quality"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    iteration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_iterations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    clarity_pass = Column(Boolean, nullable=False)
    clarity_message = Column(Text, nullable=True)

    unambiguity_pass = Column(Boolean, nullable=False)
    unambiguity_message = Column(Text, nullable=True)

    consistency_pass = Column(Boolean, nullable=False)
    consistency_message = Column(Text, nullable=True)

    answer_format_pass = Column(Boolean, nullable=False)
    answer_format_message = Column(Text, nullable=True)

    language_correctness_pass = Column(Boolean, nullable=False)
    language_correctness_message = Column(Text, nullable=True)

    verdict = Column(String(20), nullable=False, index=True)

    diagnostic_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        default=utc_now,
        nullable=False,
    )

    rejection_reasons = relationship(
        "RejectionReason",
        back_populates="quality_profile",
        cascade="all, delete-orphan",
    )

    iteration = relationship("TaskIteration", back_populates="quality_profile")

    __table_args__ = (
        Index("ix_quality_verdict", "verdict"),
    )

    @property
    def is_accepted(self) -> bool:
        """Возвращает True, если формулировка принята по всем критериям."""

        return self.verdict == "accepted"

    def __repr__(self) -> str:
        return (
            f"<TaskQuality iteration_id={self.iteration_id} "
            f"verdict={self.verdict}>"
        )
