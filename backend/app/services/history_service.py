"""
Сервис получения списка и истории заданий с фильтрацией и пагинацией.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.task import Task
from backend.app.models.task_iteration import TaskIteration
from backend.app.models.task_quality import TaskQuality
from backend.app.schemas.task import (
    HistoryItem,
    HistoryResponse,
    TaskListItem,
    TaskListResponse,
    GenerateTaskSuccessResponse,
    QualityProfileResponse,
    CriterionResult,
    RejectionReasonResponse,
    IterationSummary,
)


async def get_task_history(
        session: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        task_type: Optional[int] = None,
        subtype: Optional[str] = None,
        status: Optional[str] = None,
) -> HistoryResponse:
    """Пагинированная история генераций, sorted by created_at DESC."""

    base = select(Task)
    count_q = select(func.count(Task.id))

    if task_type is not None:
        base = base.where(Task.task_type == task_type)
        count_q = count_q.where(Task.task_type == task_type)
    if subtype is not None:
        base = base.where(Task.subtype == subtype)
        count_q = count_q.where(Task.subtype == subtype)
    if status is not None:
        base = base.where(Task.status == status)
        count_q = count_q.where(Task.status == status)

    total = (await session.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    stmt = base.order_by(Task.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    tasks = result.scalars().all()

    items = [
        HistoryItem(
            task_id=t.id,
            task_type=t.task_type,
            subtype=t.subtype,
            status=t.status,
            created_at=t.created_at,
            total_iterations=t.total_iterations,
        )
        for t in tasks
    ]

    return HistoryResponse(total=total, page=page, page_size=page_size, items=items)


async def get_task_list(
        session: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        task_type: Optional[int] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
) -> TaskListResponse:
    """Пагинированный список заданий (краткие карточки), sorted by created_at DESC."""

    base = select(Task)
    count_q = select(func.count(Task.id))

    if status is not None:
        base = base.where(Task.status == status)
        count_q = count_q.where(Task.status == status)
    if task_type is not None:
        base = base.where(Task.task_type == task_type)
        count_q = count_q.where(Task.task_type == task_type)
    if created_from is not None:
        base = base.where(Task.created_at >= created_from)
        count_q = count_q.where(Task.created_at >= created_from)
    if created_to is not None:
        base = base.where(Task.created_at <= created_to)
        count_q = count_q.where(Task.created_at <= created_to)

    total = (await session.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    stmt = base.order_by(Task.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(stmt)
    tasks = result.scalars().all()

    items = [
        TaskListItem(
            task_id=t.id,
            task_type=t.task_type,
            subtype=t.subtype,
            status=t.status,
            reference_answer=t.reference_answer,
            created_at=t.created_at,
        )
        for t in tasks
    ]

    return TaskListResponse(total=total, page=page, page_size=page_size, items=items)


def build_task_response(task: Task) -> GenerateTaskSuccessResponse:
    """Конвертирует ORM-объект Task (с загруженными связями) в DTO ответа."""

    quality_profile = None
    rejection_reasons_resp: list[RejectionReasonResponse] = []

    sorted_iters = sorted(task.iterations, key=lambda i: i.iteration_number)
    for it in reversed(sorted_iters):
        if it.quality_profile:
            qp = it.quality_profile
            quality_profile = QualityProfileResponse(
                clarity=CriterionResult(**{"pass": qp.clarity_pass, "message": qp.clarity_message}),
                unambiguity=CriterionResult(**{"pass": qp.unambiguity_pass, "message": qp.unambiguity_message}),
                consistency=CriterionResult(**{"pass": qp.consistency_pass, "message": qp.consistency_message}),
                answer_format=CriterionResult(**{"pass": qp.answer_format_pass, "message": qp.answer_format_message}),
                language_correctness=CriterionResult(
                    **{"pass": qp.language_correctness_pass, "message": qp.language_correctness_message}),
                verdict=qp.verdict,
                diagnostic_message=qp.diagnostic_message,
            )
            rejection_reasons_resp = [
                RejectionReasonResponse(criterion=rr.criterion, description=rr.description)
                for rr in qp.rejection_reasons
            ]
            break

    iterations_resp = [
        IterationSummary(
            attempt_no=it.iteration_number,
            status=it.status,
            quality_verdict=it.quality_profile.verdict if it.quality_profile else None,
            failure_reason=it.failure_reason,
        )
        for it in sorted_iters
    ]

    return GenerateTaskSuccessResponse(
        task_id=task.id,
        task_type=task.task_type,
        subtype=task.subtype,
        status=task.status,
        parameters=task.parameters or {},
        reference_answer=task.reference_answer or 0,
        final_wording=task.final_wording,
        quality_profile=quality_profile,
        rejection_reasons=rejection_reasons_resp,
        iterations=iterations_resp,
        created_at=task.created_at,
    )


async def get_task_by_id(
        session: AsyncSession,
        task_id: UUID,
) -> Optional[GenerateTaskSuccessResponse]:
    """Получает полную карточку задания по ID."""

    stmt = (
        select(Task)
        .where(Task.id == task_id)
        .options(
            selectinload(Task.iterations)
            .selectinload(TaskIteration.quality_profile)
            .selectinload(TaskQuality.rejection_reasons),
        )
    )
    result = await session.execute(stmt)
    task = result.scalar_one_or_none()
    if task is None:
        return None
    return build_task_response(task)
