"""
Общие Pydantic-схемы и перечисления, используемые в API.

Содержит статусы заданий, коды ошибок, критерии качества,
форматы экспорта и типы LLM-вызовов.
"""

from enum import Enum

from pydantic import BaseModel


class TaskStatus(str, Enum):
    """Возможные статусы задания после завершения конвейера генерации."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


class ErrorCode(str, Enum):
    """Машиночитаемые коды ошибок, возвращаемые в JSON-ответах API."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_TASK_TYPE = "INVALID_TASK_TYPE"
    INVALID_SUBTYPE = "INVALID_SUBTYPE"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    PARAM_RETRY_EXHAUSTED = "PARAM_RETRY_EXHAUSTED"
    LLM_GENERATION_FAILED = "LLM_GENERATION_FAILED"
    LLM_VALIDATION_FAILED = "LLM_VALIDATION_FAILED"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    UNEXPECTED_INTERNAL_ERROR = "UNEXPECTED_INTERNAL_ERROR"


class QualityCriterion(str, Enum):
    """Критерии оценки качества формулировки задания."""

    CLARITY = "clarity"
    UNAMBIGUITY = "unambiguity"
    CONSISTENCY = "consistency"
    ANSWER_FORMAT = "answer_format"
    LANGUAGE_CORRECTNESS = "language_correctness"
    NUMERIC_MATCH = "numeric_match"


class ExportFormat(str, Enum):
    """Поддерживаемые форматы экспорта задания."""

    JSON = "json"
    TXT = "txt"
    PDF = "pdf"


class LlmCallType(str, Enum):
    """Типы вызовов LLM, фиксируемые в журнале."""

    WORDING_GENERATION = "wording_generation"
    SEMANTIC_VALIDATION = "semantic_validation"


class RejectionReasonSchema(BaseModel):
    """Одна причина отказа, привязанная к конкретному критерию."""

    criterion: QualityCriterion
    description: str | None = None
