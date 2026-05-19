"""Централизованная обработка ошибок FastAPI."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.exceptions import (
    DomainException,
    InvalidTaskTypeError,
    InvalidSubtypeError,
    InvalidDateRangeError,
    ParamRetryExhaustedError,
    LlmGenerationError,
    LlmValidationError,
    LlmTimeoutError,
)
from backend.app.schemas.common import ErrorCode

_STATUS_MAP: dict[type[DomainException], int] = {
    InvalidTaskTypeError: 400,
    InvalidSubtypeError: 400,
    InvalidDateRangeError: 400,
    ParamRetryExhaustedError: 500,
    LlmGenerationError: 500,
    LlmValidationError: 500,
    LlmTimeoutError: 504,
}


def _build_error_body(exc: DomainException) -> dict:
    """Формирует стандартное тело ошибки."""

    body: dict = {
        "error": {
            "code": exc.error_code.value,
            "message": exc.message,
            "details": None,
        }
    }
    if exc.task_id is not None:
        body["error"]["details"] = {"task_id": str(exc.task_id)}
    return body


logger = logging.getLogger(__name__)


async def _handle_domain_exception(request: Request, exc: DomainException) -> JSONResponse:
    """Обрабатывает доменные исключения и возвращает JSON с кодом и сообщением ошибки."""

    status_code = _STATUS_MAP.get(type(exc), 500)
    logger.error(
        "%s: %s (task_id=%s, status=%d)",
        exc.error_code.value, exc.message, exc.task_id, status_code,
    )
    return JSONResponse(
        status_code=status_code,
        content=_build_error_body(exc),
    )


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Обрабатывает ошибки валидации Pydantic и возвращает 422 в едином формате."""

    errors = []
    for err in exc.errors():
        clean_err = {}
        for key, value in err.items():
            if isinstance(value, bytes):
                clean_err[key] = value.decode("utf-8", errors="replace")
            else:
                clean_err[key] = value
        errors.append(clean_err)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": ErrorCode.VALIDATION_ERROR.value,
                "message": "Неверные параметры запроса.",
                "details": {"violations": errors},
            }
        },
    )


async def _handle_rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Возвращает 429 в едином формате {error: {code, message}} при срабатывании rate limit."""

    logger.warning(
        "Rate limit превышен: path=%s client=%s limit=%s",
        request.url.path,
        request.client.host if request.client else "unknown",
        exc.detail,
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": ErrorCode.RATE_LIMIT_EXCEEDED.value,
                "message": (
                    "Превышен лимит запросов. Попробуйте позже. "
                    f"Ограничение: {exc.detail}."
                ),
                "details": None,
            }
        },
        headers={"Retry-After": "60"},
    )


async def _handle_sqlalchemy_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Обрабатывает непойманные ошибки SQLAlchemy/asyncpg и возвращает JSON 500."""

    logger.exception(
        "Непредвиденная ошибка БД: path=%s, exc_type=%s",
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": ErrorCode.UNEXPECTED_INTERNAL_ERROR.value,
                "message": "Внутренняя ошибка базы данных. Запрос не был выполнен.",
                "details": None,
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Регистрирует все обработчики ошибок на экземпляре FastAPI."""

    app.add_exception_handler(DomainException, _handle_domain_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit_exceeded)
    app.add_exception_handler(SQLAlchemyError, _handle_sqlalchemy_error)
