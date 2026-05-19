"""
Оркестратор полного конвейера генерации задания ЕГЭ.

Логика разбита на самостоятельные этапы:
  execute → валидация входа → _run_pipeline → _prepare → цикл _run_iteration
  каждая итерация → _save_quality → _finalize_accepted | продолжение цикла
  после исчерпания итераций → _finalize_rejected.

execute обрабатывает доменные/непредвиденные исключения единообразно
и обновляет метрики/статус task; _run_pipeline владеет внутренним состоянием
итераций без побочного кода.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import (
    DomainException,
    InvalidTaskTypeError,
    InvalidSubtypeError,
    LlmGenerationError,
    LlmTimeoutError,
    LlmValidationError,
)
from backend.app.core.metrics import (
    task_generation_duration_seconds,
    tasks_generated_total,
)
from backend.app.generators.task11 import SUBTYPES_11
from backend.app.generators.task7 import SUBTYPES_7
from backend.app.models.mixins import utc_now
from backend.app.models.rejection_reason import RejectionReason
from backend.app.models.task import Task
from backend.app.models.task_iteration import TaskIteration
from backend.app.models.task_quality import TaskQuality
from backend.app.schemas.task import GenerateTaskSuccessResponse
from backend.app.services.history_service import get_task_by_id
from backend.app.services.llm_adapter import get_llm_adapter
from backend.app.services.param_generator import ParamGeneratorService
from backend.app.services.wording_generator import WordingGenerator
from backend.app.services.wording_numeric_check import (
    find_missing_params,
    format_feedback as format_numeric_feedback,
)
from backend.app.services.wording_validator import (
    ValidationResult,
    WordingValidator,
)

logger = logging.getLogger(__name__)

SUPPORTED_TYPES: dict[int, list[str]] = {
    7: SUBTYPES_7,
    11: SUBTYPES_11,
}

MAX_LLM_ITERATIONS = 3


@dataclass
class _PipelineContext:
    """Все данные, разделяемые между итерациями цикла."""

    task: Task
    task_type: int
    subtype: str
    params: dict
    target_param: str
    answer: int
    wording_gen: WordingGenerator
    wording_val: WordingValidator
    previous_feedbacks: list[str] = field(default_factory=list)
    previous_wording: Optional[str] = None
    last_wording: Optional[str] = None  # последняя сгенерированная (любого статуса)


class TaskOrchestrator:
    """Оркестратор конвейера генерации задания."""

    def __init__(self) -> None:
        self._param_generator = ParamGeneratorService()

    async def execute(
            self,
            session: AsyncSession,
            task_type: int,
            subtype: Optional[str] = None,
    ) -> GenerateTaskSuccessResponse:
        """Выполняет полный конвейер генерации задания."""

        start_time = time.monotonic()
        logger.info("Генерация задания: task_type=%d, subtype=%s", task_type, subtype)

        self._validate_input(task_type, subtype)
        task = await self._create_task_row(session, task_type, subtype)

        try:
            result = await self._run_pipeline(session, task, task_type, subtype)
            self._record_metrics(task_type, result.status, start_time)
            logger.info(
                "Задание завершено: task_id=%s, status=%s, duration=%.2fs",
                task.id, result.status, time.monotonic() - start_time,
            )
            return result
        except DomainException as e:
            e.task_id = task.id
            await self._mark_task_error(session, task, e.error_code.value, e.message)
            self._record_metrics(task_type, "error", start_time)
            logger.error(
                "Ошибка генерации: task_id=%s, error=%s, duration=%.2fs",
                task.id, e.error_code.value, time.monotonic() - start_time,
            )
            raise
        except Exception as e:
            await self._mark_task_error(session, task, "UNEXPECTED_INTERNAL_ERROR", str(e))
            self._record_metrics(task_type, "error", start_time)
            logger.exception(
                "Непредвиденная ошибка: task_id=%s, duration=%.2fs",
                task.id, time.monotonic() - start_time,
            )
            raise

    @staticmethod
    def _validate_input(task_type: int, subtype: Optional[str]) -> None:
        """Проверяет, что тип и подтип поддерживаются."""

        if task_type not in SUPPORTED_TYPES:
            raise InvalidTaskTypeError(
                f"Тип задания {task_type} не поддерживается. "
                f"Допустимые: {sorted(SUPPORTED_TYPES.keys())}."
            )
        if subtype is not None and subtype not in SUPPORTED_TYPES[task_type]:
            raise InvalidSubtypeError(
                f"Подтип '{subtype}' не поддерживается для типа {task_type}. "
                f"Допустимые: {SUPPORTED_TYPES[task_type]}."
            )

    @staticmethod
    async def _create_task_row(
            session: AsyncSession, task_type: int, subtype: Optional[str],
    ) -> Task:
        """Создаёт начальную запись Task со status='error' — она будет
        обновлена при accept/reject или останется error при сбое."""

        task = Task(
            task_type=task_type,
            subtype=subtype or "pending",
            status="error",
        )
        session.add(task)
        await session.flush()
        return task

    async def _prepare_pipeline_context(
            self,
            session: AsyncSession,
            task: Task,
            task_type: int,
            subtype: Optional[str],
    ) -> _PipelineContext:
        """Генерирует параметры/ответ и собирает контекст итераций."""

        params, target_param, answer, resolved_subtype = (
            await self._param_generator.generate(
                session, task.id, task_type, subtype,
            )
        )

        task.subtype = resolved_subtype
        task.parameters = params
        task.reference_answer = answer
        await session.flush()

        gen_adapter = get_llm_adapter(
            settings.llm_generation_provider, purpose="generation",
        )
        val_adapter = get_llm_adapter(
            settings.llm_validation_provider, purpose="validation",
        )

        return _PipelineContext(
            task=task,
            task_type=task_type,
            subtype=resolved_subtype,
            params=params,
            target_param=target_param,
            answer=answer,
            wording_gen=WordingGenerator(gen_adapter),
            wording_val=WordingValidator(val_adapter),
        )

    async def _run_pipeline(
            self,
            session: AsyncSession,
            task: Task,
            task_type: int,
            subtype: Optional[str],
    ) -> GenerateTaskSuccessResponse:
        """Гоняет цикл «генерация → валидация → numeric-check» до MAX_LLM_ITERATIONS."""

        ctx = await self._prepare_pipeline_context(session, task, task_type, subtype)

        for iter_num in range(1, MAX_LLM_ITERATIONS + 1):
            logger.info("Итерация %d/%d: task_id=%s", iter_num, MAX_LLM_ITERATIONS, task.id)

            accepted_response = await self._run_iteration(session, ctx, iter_num)
            if accepted_response is not None:
                return accepted_response

        return await self._finalize_rejected(session, ctx)

    async def _run_iteration(
            self,
            session: AsyncSession,
            ctx: _PipelineContext,
            iter_num: int,
    ) -> Optional[GenerateTaskSuccessResponse]:
        """Одна итерация. Возвращает finalized-response при accept, иначе None."""

        iteration = TaskIteration(
            task_id=ctx.task.id,
            iteration_number=iter_num,
            status="error",
            started_at=utc_now(),
        )
        session.add(iteration)
        await session.flush()

        wording = await self._generate_wording(session, ctx, iteration)
        iteration.wording = wording
        ctx.last_wording = wording

        validation_result = await self._validate_wording(session, ctx, iteration, wording)
        quality = await self._save_quality(session, iteration, validation_result)

        numeric_feedback = await self._check_numeric_match(
            session, ctx, iteration, quality, wording, validation_result, iter_num,
        )

        if validation_result.is_accepted and numeric_feedback is None:
            return await self._finalize_accepted(session, ctx, iteration, wording, iter_num)

        self._record_rejected_iteration(
            ctx, iteration, validation_result, numeric_feedback, wording, iter_num,
        )
        await session.flush()
        return None

    @staticmethod
    async def _generate_wording(
            session: AsyncSession,
            ctx: _PipelineContext,
            iteration: TaskIteration,
    ) -> str:
        """Шаг генерации формулировки. Помечает итерацию error при сбое LLM."""

        try:
            return await ctx.wording_gen.generate(
                session=session,
                task_id=ctx.task.id,
                iteration_id=iteration.id,
                task_type=ctx.task_type,
                subtype=ctx.subtype,
                params=ctx.params,
                target_param=ctx.target_param,
                reference_answer=ctx.answer,
                previous_feedbacks=ctx.previous_feedbacks or None,
                previous_wording=ctx.previous_wording,
            )
        except (LlmGenerationError, LlmTimeoutError) as exc:
            iteration.status = "error"
            iteration.failure_stage = "generation"
            iteration.failure_reason = (
                "Таймаут LLM при генерации формулировки"
                if isinstance(exc, LlmTimeoutError)
                else "Сбой генерации формулировки LLM"
            )
            iteration.finished_at = utc_now()
            await session.flush()
            raise

    @staticmethod
    async def _validate_wording(
            session: AsyncSession,
            ctx: _PipelineContext,
            iteration: TaskIteration,
            wording: str,
    ) -> ValidationResult:
        """Шаг LLM-валидации. Помечает итерацию error при сбое LLM."""

        try:
            return await ctx.wording_val.validate(
                session=session,
                task_id=ctx.task.id,
                iteration_id=iteration.id,
                task_type=ctx.task_type,
                subtype=ctx.subtype,
                wording=wording,
                reference_answer=ctx.answer,
            )
        except (LlmValidationError, LlmTimeoutError) as exc:
            iteration.status = "error"
            iteration.failure_stage = "validation"
            iteration.failure_reason = (
                "Таймаут LLM при валидации формулировки"
                if isinstance(exc, LlmTimeoutError)
                else "Сбой семантической валидации LLM"
            )
            iteration.finished_at = utc_now()
            await session.flush()
            raise

    @staticmethod
    async def _save_quality(
            session: AsyncSession,
            iteration: TaskIteration,
            r: ValidationResult,
    ) -> TaskQuality:
        """Сохраняет TaskQuality и RejectionReason'ы по неуспешным критериям LLM-валидатора."""

        quality = TaskQuality(
            iteration_id=iteration.id,
            clarity_pass=r.clarity_pass,
            clarity_message=r.clarity_message,
            unambiguity_pass=r.unambiguity_pass,
            unambiguity_message=r.unambiguity_message,
            consistency_pass=r.consistency_pass,
            consistency_message=r.consistency_message,
            answer_format_pass=r.answer_format_pass,
            answer_format_message=r.answer_format_message,
            language_correctness_pass=r.language_correctness_pass,
            language_correctness_message=r.language_correctness_message,
            verdict=r.verdict,
            diagnostic_message=r.diagnostic_message,
        )
        session.add(quality)
        await session.flush()

        for criterion_name, message in r.failed_criteria():
            session.add(RejectionReason(
                quality_profile_id=quality.id,
                criterion=criterion_name,
                description=message,
            ))
        await session.flush()
        return quality

    @staticmethod
    async def _check_numeric_match(
            session: AsyncSession,
            ctx: _PipelineContext,
            iteration: TaskIteration,
            quality: TaskQuality,
            wording: str,
            validation_result: ValidationResult,
            iter_num: int,
    ) -> Optional[str]:
        """Детерминированная проверка чисел. Запускается только если LLM приняла.

        При обнаружении пропусков добавляет RejectionReason и возвращает
        текст замечания. Если параметры на месте — возвращает None.
        """

        if not validation_result.is_accepted:
            return None

        missing = find_missing_params(wording, ctx.params, ctx.target_param)
        if not missing:
            return None

        feedback = format_numeric_feedback(missing)
        logger.warning(
            "Итерация %d: LLM-валидатор принял, но числовая проверка "
            "обнаружила отсутствующие параметры: %s (task_id=%s)",
            iter_num, missing, ctx.task.id,
        )
        session.add(RejectionReason(
            quality_profile_id=quality.id,
            criterion="numeric_match",
            description=feedback,
        ))
        await session.flush()
        return feedback

    @staticmethod
    async def _finalize_accepted(
            session: AsyncSession,
            ctx: _PipelineContext,
            iteration: TaskIteration,
            wording: str,
            iter_num: int,
    ) -> GenerateTaskSuccessResponse:
        """Помечает итерацию и задачу как accepted, коммитит и возвращает карточку."""

        logger.info("Итерация %d accepted: task_id=%s", iter_num, ctx.task.id)
        iteration.status = "accepted"
        iteration.finished_at = utc_now()
        ctx.task.status = "accepted"
        ctx.task.final_wording = wording
        ctx.task.total_iterations = iter_num
        await session.commit()
        return await _load_response_or_raise(session, ctx.task.id)

    @staticmethod
    def _record_rejected_iteration(
            ctx: _PipelineContext,
            iteration: TaskIteration,
            validation_result: ValidationResult,
            numeric_feedback: Optional[str],
            wording: str,
            iter_num: int,
    ) -> None:
        """Обновляет итерацию как rejected и копит feedback для следующей попытки."""

        feedback = validation_result.feedback_text()
        if numeric_feedback:
            feedback = (
                f"{feedback}\n{numeric_feedback}" if feedback else numeric_feedback
            )
        logger.info(
            "Итерация %d rejected: task_id=%s, причины: %s",
            iter_num, ctx.task.id, feedback,
        )
        iteration.status = "rejected"
        iteration.finished_at = utc_now()
        iteration.failure_reason = feedback or None
        if feedback:
            ctx.previous_feedbacks.append(feedback)
        ctx.previous_wording = wording

    @staticmethod
    async def _finalize_rejected(
            session: AsyncSession, ctx: _PipelineContext,
    ) -> GenerateTaskSuccessResponse:
        """Все итерации исчерпаны — фиксируем задачу как rejected."""

        ctx.task.status = "rejected"
        ctx.task.final_wording = ctx.last_wording
        ctx.task.total_iterations = MAX_LLM_ITERATIONS
        await session.commit()
        return await _load_response_or_raise(session, ctx.task.id)

    @staticmethod
    async def _mark_task_error(
            session: AsyncSession, task: Task, code: str, message: str,
    ) -> None:
        task.status = "error"
        task.error_code = code
        task.error_message = message
        await session.commit()

    @staticmethod
    def _record_metrics(task_type: int, status: str, start_time: float) -> None:
        duration = time.monotonic() - start_time
        task_generation_duration_seconds.observe(duration)
        tasks_generated_total.labels(task_type=str(task_type), status=status).inc()


async def _load_response_or_raise(
        session: AsyncSession, task_id,
) -> GenerateTaskSuccessResponse:
    """Загружает карточку задачи после commit; падает, если запись внезапно пропала."""

    response = await get_task_by_id(session, task_id)
    if response is None:
        raise RuntimeError(
            f"Не удалось загрузить задание после коммита: task_id={task_id}"
        )
    return response
