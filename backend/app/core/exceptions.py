"""Иерархия доменных исключений приложения."""

from __future__ import annotations

from uuid import UUID

from backend.app.schemas.common import ErrorCode


class DomainException(Exception):
    """Базовое исключение для всех доменных ошибок."""

    error_code: ErrorCode
    message: str
    task_id: UUID | None

    def __init__(self, message: str, *, task_id: UUID | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.task_id = task_id


class InvalidTaskTypeError(DomainException):
    """Запрошен неподдерживаемый тип задания ЕГЭ."""

    error_code = ErrorCode.INVALID_TASK_TYPE


class InvalidSubtypeError(DomainException):
    """Запрошен неподдерживаемый подтип задания для указанного типа."""

    error_code = ErrorCode.INVALID_SUBTYPE


class InvalidDateRangeError(DomainException):
    """Начало периода фильтрации позже его окончания."""

    error_code = ErrorCode.INVALID_DATE_RANGE


class ParamRetryExhaustedError(DomainException):
    """Все попытки генерации допустимых параметров исчерпаны."""

    error_code = ErrorCode.PARAM_RETRY_EXHAUSTED


class LlmGenerationError(DomainException):
    """Сбой при вызове LLM для генерации формулировки задания."""

    error_code = ErrorCode.LLM_GENERATION_FAILED


class LlmValidationError(DomainException):
    """Сбой при вызове LLM для семантической валидации формулировки."""

    error_code = ErrorCode.LLM_VALIDATION_FAILED


class LlmTimeoutError(DomainException):
    """Превышено время ожидания ответа от LLM."""

    error_code = ErrorCode.LLM_TIMEOUT
