"""
Pydantic-схемы для запросов и ответов API генерации заданий.

Описывает структуры данных для: генерации задания, профиля качества,
итераций, истории, списка заданий и стандартного формата ошибки.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GenerateTaskRequest(BaseModel):
    """Запрос на генерацию одного задания ЕГЭ."""

    task_type: int = Field(..., description="Тип задания ЕГЭ (7 или 11)")
    subtype: Optional[str] = Field(None, description="Подтип задания (опционален)")


class CriterionResult(BaseModel):
    """Результат проверки одного критерия качества."""

    pass_: bool = Field(..., alias="pass")
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


class QualityProfileResponse(BaseModel):
    """Профиль качества формулировки (5 булевых критериев)."""

    clarity: CriterionResult
    unambiguity: CriterionResult
    consistency: CriterionResult
    answer_format: CriterionResult
    language_correctness: CriterionResult
    verdict: str
    diagnostic_message: Optional[str] = None


class RejectionReasonResponse(BaseModel):
    """Причина отклонения формулировки."""

    criterion: str
    description: str


class IterationSummary(BaseModel):
    """Суммарная информация об одной итерации."""

    attempt_no: int
    status: str
    quality_verdict: Optional[str] = None
    failure_reason: Optional[str] = None


class GenerateTaskSuccessResponse(BaseModel):
    """Ответ на запрос генерации задания (200 OK)."""

    task_id: UUID
    task_type: int
    subtype: str
    status: str
    parameters: dict
    reference_answer: int
    final_wording: Optional[str] = None
    quality_profile: Optional[QualityProfileResponse] = None
    rejection_reasons: list[RejectionReasonResponse] = Field(default_factory=list)
    iterations: list[IterationSummary] = Field(default_factory=list)
    created_at: datetime


class HistoryItem(BaseModel):
    """Элемент истории генераций."""

    task_id: UUID
    task_type: int
    subtype: str
    status: str
    created_at: datetime
    total_iterations: Optional[int] = None


class HistoryResponse(BaseModel):
    """Пагинированный ответ истории."""

    total: int
    page: int
    page_size: int
    items: list[HistoryItem]


class TaskListItem(BaseModel):
    """Краткая карточка задания для списка."""

    task_id: UUID
    task_type: int
    subtype: str
    status: str
    reference_answer: Optional[int] = None
    created_at: datetime


class TaskListResponse(BaseModel):
    """Пагинированный список заданий."""

    total: int
    page: int
    page_size: int
    items: list[TaskListItem]


class ErrorDetail(BaseModel):
    """Детали ошибки."""

    task_id: Optional[str] = None


class ErrorBody(BaseModel):
    """Тело ошибки."""

    code: str
    message: str
    details: Optional[ErrorDetail] = None


class ErrorResponse(BaseModel):
    """Стандартный формат ошибки API."""

    error: ErrorBody
