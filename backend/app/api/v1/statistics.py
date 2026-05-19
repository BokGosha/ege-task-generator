"""Эндпоинт агрегированной статистики генерации заданий."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.schemas.statistics import StatisticsResponse
from backend.app.services import statistics_service

router = APIRouter(prefix="/statistics", tags=["Statistics"])


@router.get("", response_model=StatisticsResponse)
async def get_statistics(
        date_from: Optional[datetime] = Query(None, alias="from", description="Начало периода (включительно)"),
        date_to: Optional[datetime] = Query(None, alias="to", description="Конец периода (включительно)"),
        session: AsyncSession = Depends(get_db),
) -> StatisticsResponse:
    """Агрегированная статистика генерации заданий с опциональными фильтрами периода."""

    return await statistics_service.get_statistics(
        session,
        date_from=date_from,
        date_to=date_to,
    )
