"""Централизованная настройка логирования."""

import contextvars
import logging
import sys

from pythonjsonlogger import json as jsonlogger

from backend.app.core.config import settings

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-",
)


class RequestIDFilter(logging.Filter):
    """Внедряет request_id в каждую лог-запись."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        return True


def setup_logging() -> None:
    """Настраивает корневой логгер: JSON в stdout."""

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
        },
        json_ensure_ascii=False,
        static_fields={"service": "ege-api"},
    )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIDFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
