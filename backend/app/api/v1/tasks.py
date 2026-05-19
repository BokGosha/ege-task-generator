"""Эндпоинты для генерации и просмотра заданий ЕГЭ."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.rate_limit import limiter
from backend.app.schemas.task import (
    GenerateTaskRequest,
    GenerateTaskSuccessResponse,
    HistoryResponse,
    TaskListResponse,
)
from backend.app.services import history_service
from backend.app.services.task_orchestrator import TaskOrchestrator

router = APIRouter(prefix="/tasks", tags=["Tasks"])

_orchestrator = TaskOrchestrator()


@router.post("/generate", response_model=GenerateTaskSuccessResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def generate_task(
        request: Request,
        body: GenerateTaskRequest,
        session: AsyncSession = Depends(get_db),
) -> GenerateTaskSuccessResponse:
    """
    Генерация одного задания ЕГЭ по информатике.
    Возвращает полный результат: параметры, ответ, формулировку,
    профиль качества и историю итераций.

    Эндпоинт защищён rate limit'ом.
    Лимит применяется на IP клиента через slowapi middleware.
    """

    return await _orchestrator.execute(
        session=session,
        task_type=body.task_type,
        subtype=body.subtype,
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
        page: int = Query(1, ge=1, description="Номер страницы"),
        page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
        task_type: Optional[int] = Query(None, description="Фильтр по типу задания"),
        subtype: Optional[str] = Query(None, description="Фильтр по подтипу"),
        status: Optional[str] = Query(None, description="Фильтр по статусу"),
        session: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    """История генераций с пагинацией, отсортированная по дате (DESC)."""

    return await history_service.get_task_history(
        session,
        page=page,
        page_size=page_size,
        task_type=task_type,
        subtype=subtype,
        status=status,
    )


@router.get("/{task_id}", response_model=GenerateTaskSuccessResponse)
async def get_task_card(
        task_id: UUID,
        session: AsyncSession = Depends(get_db),
) -> GenerateTaskSuccessResponse:
    """Полная карточка задания по ID."""

    result = await history_service.get_task_by_id(session, task_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "TASK_NOT_FOUND",
                    "message": f"Задание с id={task_id} не найдено.",
                }
            },
        )
    return result


@router.get("", response_model=TaskListResponse)
async def get_tasks_list(
        page: int = Query(1, ge=1, description="Номер страницы"),
        page_size: int = Query(20, ge=1, le=100, description="Размер страницы"),
        status: Optional[str] = Query(None, description="Фильтр по статусу"),
        task_type: Optional[int] = Query(None, description="Фильтр по типу задания"),
        created_from: Optional[datetime] = Query(None, description="Начало периода (включительно)"),
        created_to: Optional[datetime] = Query(None, description="Конец периода (включительно)"),
        session: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """Краткий список заданий с фильтрами и пагинацией."""

    return await history_service.get_task_list(
        session,
        page=page,
        page_size=page_size,
        status=status,
        task_type=task_type,
        created_from=created_from,
        created_to=created_to,
    )
