"""
ORM-модель журнала LLM-вызовов (таблица llm_calls).

Фиксирует каждый запрос к LLM: провайдер, модель, payload запроса/ответа,
статус, токены, длительность и стоимость.
"""

import uuid

from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from backend.app.core.database import Base
from backend.app.models.mixins import TimestampMixin


class LlmCall(Base, TimestampMixin):
    """Журнал каждого вызова LLM (генерация формулировки или валидация)."""

    __tablename__ = "llm_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    iteration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_iterations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    call_type = Column(String(50), nullable=False, index=True)

    provider = Column(String(50), nullable=False)

    model_name = Column(String(100), nullable=False)

    request_payload = Column(JSONB, nullable=True)

    response_payload = Column(JSONB, nullable=True)

    status = Column(String(20), nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    estimated_cost_rub = Column(Float, nullable=True)

    duration_ms = Column(Integer, nullable=True)

    task = relationship("Task", back_populates="llm_calls")
    iteration = relationship("TaskIteration", back_populates="llm_calls")

    __table_args__ = (
        Index("ix_llm_calls_task_type", "task_id", "call_type"),
        Index("ix_llm_calls_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<LlmCall id={self.id} type={self.call_type} "
            f"provider={self.provider} status={self.status}>"
        )
