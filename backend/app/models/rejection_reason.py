"""
ORM-модель причины отклонения формулировки (таблица rejection_reasons).

Каждая запись привязана к профилю качества (TaskQuality) и содержит
критерий и текстовое описание проблемы.
"""

import uuid

from sqlalchemy import Column, String, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class RejectionReason(Base):
    """Структурированная причина отклонения формулировки по конкретному критерию."""

    __tablename__ = "rejection_reasons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    quality_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_quality.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    criterion = Column(String(50), nullable=False)

    description = Column(Text, nullable=False)

    quality_profile = relationship(
        "TaskQuality",
        back_populates="rejection_reasons",
    )

    __table_args__ = (
        Index("ix_rejection_criterion", "criterion"),
        Index("ix_rejection_profile_criterion", "quality_profile_id", "criterion"),
    )

    def __repr__(self) -> str:
        return (
            f"<RejectionReason criterion={self.criterion} "
            f"profile_id={self.quality_profile_id}>"
        )
