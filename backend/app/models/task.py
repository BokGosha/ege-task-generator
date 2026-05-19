"""
ORM-модель задания ЕГЭ (таблица tasks).

Корневая сущность, связанная с итерациями, LLM-вызовами
и аудитом генерации параметров.
"""

import uuid

from sqlalchemy import Column, Integer, BigInteger, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from backend.app.core.database import Base
from backend.app.models.mixins import TimestampMixin


class Task(Base, TimestampMixin):
    """
    Корневая сущность одного запроса генерации задания ЕГЭ.
    Хранит тип, параметры, эталонный ответ и итоговый статус конвейера.
    """

    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_type = Column(Integer, nullable=False, index=True)

    subtype = Column(String(64), nullable=False, index=True)

    parameters = Column(JSONB, nullable=True)

    reference_answer = Column(BigInteger, nullable=True)

    status = Column(String(20), nullable=False, default="error", index=True)

    final_wording = Column(Text, nullable=True)

    total_iterations = Column(Integer, nullable=True)

    error_code = Column(String(64), nullable=True)

    error_message = Column(Text, nullable=True)

    iterations = relationship(
        "TaskIteration",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskIteration.iteration_number",
    )

    llm_calls = relationship(
        "LlmCall",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    param_audits = relationship(
        "ParamGenerationAudit",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_tasks_type_created", "task_type", "created_at"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_created_at_desc", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Task id={self.id} task_type={self.task_type} "
            f"status={self.status} iterations={self.total_iterations}>"
        )
