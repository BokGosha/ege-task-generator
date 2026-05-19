"""Сервис генерации параметров задания с retry-логикой и аудитом."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import ParamRetryExhaustedError, InvalidTaskTypeError
from backend.app.generators.task11 import generate_params_11, is_valid_params_11, SUBTYPES_11
from backend.app.generators.task7 import generate_params_7, is_valid_params_7, SUBTYPES_7
from backend.app.models.param_generation_audit import ParamGenerationAudit
from backend.app.services.answer_calculator import calculate_answer

logger = logging.getLogger(__name__)

_GENERATORS = {
    7: (generate_params_7, is_valid_params_7, SUBTYPES_7),
    11: (generate_params_11, is_valid_params_11, SUBTYPES_11),
}


class ParamGeneratorService:
    """Генерация и валидация параметров задания с retry до 5 попыток."""

    MAX_PARAM_ATTEMPTS = 5

    async def generate(
            self,
            session: AsyncSession,
            task_id: UUID,
            task_type: int,
            subtype: str | None = None,
    ) -> tuple[dict[str, Any], str, int, str]:
        """Генерирует валидные параметры задания."""

        gen_fn, validate_fn, _ = _GENERATORS[task_type]

        for attempt in range(1, self.MAX_PARAM_ATTEMPTS + 1):
            try:
                params, target_param, answer = gen_fn(subtype=subtype)
            except ValueError as e:
                reason = f"Ошибка генерации: {e}"
                await self._log_failed_attempt(session, task_id, attempt, reason)
                continue

            valid, reason = validate_fn(params, target_param, answer)
            if not valid:
                logger.warning(
                    "Попытка %d/%d для task_id=%s: %s",
                    attempt, self.MAX_PARAM_ATTEMPTS, task_id, reason,
                )
                await self._log_failed_attempt(session, task_id, attempt, reason)
                continue

            try:
                recomputed = calculate_answer(task_type, params["subtype"], params, target_param)
                if recomputed != answer:
                    reason = (
                        f"Кросс-проверка ответа: калькулятор={recomputed}, генератор={answer}"
                    )
                    logger.warning(
                        "Попытка %d/%d для task_id=%s: %s",
                        attempt, self.MAX_PARAM_ATTEMPTS, task_id, reason,
                    )
                    await self._log_failed_attempt(session, task_id, attempt, reason)
                    continue
            except ValueError as e:
                reason = f"Ошибка кросс-проверки: {e}"
                await self._log_failed_attempt(session, task_id, attempt, reason)
                continue

            resolved_subtype = params["subtype"]
            return params, target_param, answer, resolved_subtype

        raise ParamRetryExhaustedError(
            f"Не удалось сгенерировать допустимый набор параметров "
            f"за {self.MAX_PARAM_ATTEMPTS} попыток.",
            task_id=task_id,
        )

    async def _log_failed_attempt(
            self,
            session: AsyncSession,
            task_id: UUID,
            attempt: int,
            reason: str,
    ) -> None:
        """Записывает неудачную попытку генерации параметров."""

        audit = ParamGenerationAudit(
            task_id=task_id,
            attempt_number=attempt,
            rejection_reason=reason,
        )
        session.add(audit)
        await session.flush()
