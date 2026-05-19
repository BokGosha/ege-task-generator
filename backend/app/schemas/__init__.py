"""Пакет Pydantic-схем (DTO) для API."""

from backend.app.schemas.common import (
    TaskStatus,
    ErrorCode,
    ExportFormat,
    QualityCriterion,
    LlmCallType,
    RejectionReasonSchema,
)
from backend.app.schemas.statistics import StatisticsResponse
from backend.app.schemas.task import (
    GenerateTaskRequest,
    CriterionResult,
    QualityProfileResponse,
    RejectionReasonResponse,
    IterationSummary,
    GenerateTaskSuccessResponse,
    HistoryItem,
    HistoryResponse,
    TaskListItem,
    TaskListResponse,
    ErrorResponse,
)

__all__ = [
    "TaskStatus",
    "ErrorCode",
    "ExportFormat",
    "QualityCriterion",
    "LlmCallType",
    "RejectionReasonSchema",
    "GenerateTaskRequest",
    "CriterionResult",
    "QualityProfileResponse",
    "RejectionReasonResponse",
    "IterationSummary",
    "GenerateTaskSuccessResponse",
    "HistoryItem",
    "HistoryResponse",
    "TaskListItem",
    "TaskListResponse",
    "ErrorResponse",
    "StatisticsResponse",
]
