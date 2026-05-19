"""
Сервис агрегированной статистики — динамические запросы к базовым таблицам.
Таблица TaskStatistics не используется для чтения.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import InvalidDateRangeError
from backend.app.models.llm_call import LlmCall
from backend.app.models.rejection_reason import RejectionReason
from backend.app.models.task import Task
from backend.app.models.task_iteration import TaskIteration
from backend.app.models.task_quality import TaskQuality
from backend.app.schemas.statistics import (
    StatisticsResponse,
    StatusShares,
    RejectionReasonStatistic,
    TaskTypeStatistic,
    ModelStats,
    ModelUsageStatistic,
)


async def get_statistics(
        session: AsyncSession,
        *,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
) -> StatisticsResponse:
    """Агрегированная статистика с опциональными фильтрами периода."""

    if date_from and date_to and date_from > date_to:
        raise InvalidDateRangeError(
            "Начало периода (from) не может быть позже окончания (to)."
        )

    conditions = []
    if date_from is not None:
        conditions.append(Task.created_at >= date_from)
    if date_to is not None:
        conditions.append(Task.created_at <= date_to)

    where_clause = and_(*conditions) if conditions else True

    status_q = select(
        func.count(Task.id).label("total"),
        func.count(case((Task.status == "accepted", 1))).label("accepted"),
        func.count(case((Task.status == "rejected", 1))).label("rejected"),
        func.count(case((Task.status == "error", 1))).label("error"),
    ).where(where_clause)
    row = (await session.execute(status_q)).one()
    total = row.total or 0

    if total > 0:
        shares = StatusShares(
            accepted=row.accepted / total,
            rejected=row.rejected / total,
            error=row.error / total,
        )
    else:
        shares = StatusShares()

    avg_q = select(
        func.avg(Task.total_iterations)
    ).where(and_(where_clause, Task.total_iterations.isnot(None)))
    avg_iter = (await session.execute(avg_q)).scalar() or 0.0

    rr_q = (
        select(
            RejectionReason.criterion,
            func.count(RejectionReason.id).label("cnt"),
        )
        .select_from(RejectionReason)
        .join(TaskQuality, RejectionReason.quality_profile_id == TaskQuality.id)
        .join(TaskIteration, TaskQuality.iteration_id == TaskIteration.id)
        .join(Task, TaskIteration.task_id == Task.id)
    )
    if conditions:
        rr_q = rr_q.where(where_clause)
    rr_q = rr_q.group_by(RejectionReason.criterion).order_by(func.count(RejectionReason.id).desc()).limit(5)

    rr_rows = (await session.execute(rr_q)).all()
    top_reasons = [
        RejectionReasonStatistic(criterion=r.criterion, count=r.cnt)
        for r in rr_rows
    ]

    type_q = (
        select(Task.task_type, func.count(Task.id).label("cnt"))
        .where(where_clause)
        .group_by(Task.task_type)
        .order_by(Task.task_type)
    )
    type_rows = (await session.execute(type_q)).all()
    by_type = [
        TaskTypeStatistic(task_type=r.task_type, count=r.cnt)
        for r in type_rows
    ]

    llm_conditions = []
    if date_from is not None:
        llm_conditions.append(LlmCall.created_at >= date_from)
    if date_to is not None:
        llm_conditions.append(LlmCall.created_at <= date_to)
    llm_where = and_(*llm_conditions) if llm_conditions else True

    gen_models = await _model_stats(session, "wording_generation", llm_where)
    val_models = await _model_stats(session, "semantic_validation", llm_where)

    return StatisticsResponse(
        total_tasks=total,
        status_shares=shares,
        avg_iterations=round(float(avg_iter), 2),
        top_rejection_reasons=top_reasons,
        by_task_type=by_type,
        model_stats=ModelStats(generation=gen_models, validation=val_models),
        generated_at=datetime.now(timezone.utc),
    )


async def _model_stats(
        session: AsyncSession,
        call_type: str,
        where_clause,
) -> list[ModelUsageStatistic]:
    """Статистика по моделям для данного типа вызова."""

    q = (
        select(
            LlmCall.model_name,
            func.count(LlmCall.id).label("calls"),
            func.count(case((LlmCall.status != "success", 1))).label("failures"),
        )
        .where(and_(LlmCall.call_type == call_type, where_clause))
        .group_by(LlmCall.model_name)
    )
    rows = (await session.execute(q)).all()
    return [
        ModelUsageStatistic(model_name=r.model_name, calls=r.calls, failures=r.failures)
        for r in rows
    ]
