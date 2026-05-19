"""
ORM-модель итерации генерации (таблица task_iterations).

Каждая итерация - одна попытка цикла «генерация формулировки → валидация».
"""

import uuid

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.core.database import Base


class TaskIteration(Base):
    """Одна попытка цикла «генерация формулировки → валидация» в рамках задания."""

    __tablename__ = "task_iterations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    iteration_number = Column(Integer, nullable=False)

    wording = Column(Text, nullable=True)

    status = Column(String(20), nullable=False, index=True)

    failure_stage = Column(String(20), nullable=True)

    failure_reason = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="iterations")

    quality_profile = relationship(
        "TaskQuality",
        back_populates="iteration",
        uselist=False,
        cascade="all, delete-orphan",
    )

    llm_calls = relationship(
        "LlmCall",
        back_populates="iteration",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_iterations_task_number",
            "task_id",
            "iteration_number",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TaskIteration task_id={self.task_id} "
            f"iter={self.iteration_number} status={self.status}>"
        )
