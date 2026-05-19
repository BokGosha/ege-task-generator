"""Middleware для присвоения уникального request_id каждому HTTP-запросу."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.app.core.logging_config import request_id_ctx


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Устанавливает request_id из заголовка X-Request-ID или генерирует новый."""

    async def dispatch(
            self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        """Извлекает или генерирует request_id и сохраняет его в ContextVar."""

        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_ctx.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
