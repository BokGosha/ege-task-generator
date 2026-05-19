"""
Точка входа FastAPI-приложения.

Настраивает экземпляр FastAPI, подключает middleware (CORS, request_id),
регистрирует обработчики ошибок и маршруты API v1.
Предоставляет служебные эндпоинты: /, /health, /metrics.
"""

import logging
from contextlib import asynccontextmanager

import prometheus_client
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import PlainTextResponse

from backend.app.api.v1 import v1_router
from backend.app.core.error_handler import register_error_handlers
from backend.app.core.logging_config import setup_logging
from backend.app.core.rate_limit import limiter
from backend.app.middleware.request_id import RequestIDMiddleware

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""

    logger.info("Приложение запущено")
    yield
    logger.info("Приложение остановлено")


app = FastAPI(
    title="EGE Task Generator API",
    description="API для генерации и управления задачами ЕГЭ по информатике с автоматической проверкой качества",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

register_error_handlers(app)

app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/", tags=["Root"])
async def root():
    """Корневой эндпоинт для проверки работоспособности API."""

    return {
        "message": "EGE Task Generator API is running",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check эндпоинт для мониторинга."""

    return {"status": "healthy"}


@app.get("/metrics", tags=["Metrics"])
async def metrics():
    """Prometheus metrics endpoint."""

    data = prometheus_client.generate_latest()
    return PlainTextResponse(
        data.decode("utf-8"),
        media_type=prometheus_client.CONTENT_TYPE_LATEST,
    )
