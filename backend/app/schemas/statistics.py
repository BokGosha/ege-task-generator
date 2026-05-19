"""
Pydantic-схемы для эндпоинта агрегированной статистики.

Описывает структуры: статистика по типам заданий, долям статусов,
причинам отклонения и использованию LLM-моделей.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class RejectionReasonStatistic(BaseModel):
    """Статистика по одному критерию отклонения."""

    criterion: str
    count: int = Field(..., ge=0)


class TaskTypeStatistic(BaseModel):
    """Статистика по одному типу задания."""

    task_type: int
    count: int = Field(..., ge=0)


class ModelUsageStatistic(BaseModel):
    """Статистика использования одной модели."""

    model_name: str
    calls: int = Field(..., ge=0)
    failures: int = Field(..., ge=0)


class StatusShares(BaseModel):
    """Доли статусов как ratio [0..1]."""

    accepted: float = Field(0.0, ge=0.0, le=1.0)
    rejected: float = Field(0.0, ge=0.0, le=1.0)
    error: float = Field(0.0, ge=0.0, le=1.0)


class ModelStats(BaseModel):
    """Статистика по моделям генерации и валидации."""

    generation: list[ModelUsageStatistic] = Field(default_factory=list)
    validation: list[ModelUsageStatistic] = Field(default_factory=list)


class StatisticsResponse(BaseModel):
    """Агрегированная статистика генерации заданий."""

    total_tasks: int = Field(..., ge=0)
    status_shares: StatusShares
    avg_iterations: float = Field(..., ge=0.0)
    top_rejection_reasons: list[RejectionReasonStatistic] = Field(default_factory=list)
    by_task_type: list[TaskTypeStatistic] = Field(default_factory=list)
    model_stats: ModelStats
    generated_at: datetime
