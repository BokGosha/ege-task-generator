"""Маршруты API версии 1."""

from fastapi import APIRouter

from backend.app.api.v1 import tasks, statistics, export

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(tasks.router)
v1_router.include_router(statistics.router)
v1_router.include_router(export.router)
