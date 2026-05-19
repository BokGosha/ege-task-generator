"""
Сервис генерации формулировки задания через LLM.

Логика сборки промпта декларативна: основной шаблон, формализм и
few-shot примеры лежат в backend/app/resources/prompts/ и подгружаются
через ``prompt_loader``. Это позволяет править доменные тексты без
изменения кода — см. README в каталоге resources/prompts.
"""

import logging
import time
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import LlmGenerationError, LlmTimeoutError
from backend.app.services.llm_adapter import BaseLlmAdapter
from backend.app.services.llm_logger import log_llm_call
from backend.app.services.prompt_loader import load_prompt, render

logger = logging.getLogger(__name__)


class WordingGenerator:
    """Генерация текста формулировки задания ЕГЭ через LLM."""

    def __init__(self, adapter: BaseLlmAdapter) -> None:
        self._adapter = adapter

    async def generate(
            self,
            session: AsyncSession,
            task_id: UUID,
            iteration_id: UUID,
            task_type: int,
            subtype: str,
            params: dict[str, Any],
            target_param: str,
            reference_answer: int,
            previous_feedbacks: Optional[list[str]] = None,
            previous_wording: Optional[str] = None,
    ) -> str:
        """Генерирует текст формулировки задания.

        ``previous_feedbacks`` — список замечаний валидатора по ВСЕМ
        прошлым отклонённым итерациям (по порядку). ``previous_wording`` —
        текст самой последней отклонённой формулировки. Если оба заданы,
        в промпт добавляется секция с историей ошибок и последний
        отклонённый текст как ориентир для исправления (режим regenerate).
        """

        prompt = self._build_prompt(
            task_type, subtype, params, target_param,
            reference_answer, previous_feedbacks, previous_wording,
        )

        request_payload = {"prompt": prompt, "task_type": task_type, "subtype": subtype}
        start = time.monotonic()

        try:
            wording = await self._adapter.generate_text(prompt)
            duration_ms = int((time.monotonic() - start) * 1000)

            token_usage = self._adapter.last_token_usage or {}

            await log_llm_call(
                session,
                task_id=task_id,
                iteration_id=iteration_id,
                call_type="wording_generation",
                provider=self._adapter.provider,
                model_name=self._adapter.model_name,
                request_payload=request_payload,
                response_payload={"wording": wording[:500]},
                status="success",
                prompt_tokens=token_usage.get("prompt_tokens"),
                completion_tokens=token_usage.get("completion_tokens"),
                duration_ms=duration_ms,
            )

            return wording

        except LlmGenerationError:
            raise
        except LlmTimeoutError as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error("Таймаут при генерации формулировки: %s", e)

            await log_llm_call(
                session,
                task_id=task_id,
                iteration_id=iteration_id,
                call_type="wording_generation",
                provider=self._adapter.provider,
                model_name=self._adapter.model_name,
                request_payload=request_payload,
                response_payload=None,
                status="error",
                error_message=str(e),
                duration_ms=duration_ms,
            )

            raise LlmTimeoutError(e.message, task_id=task_id) from e
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error("Ошибка генерации формулировки: %s", e)

            await log_llm_call(
                session,
                task_id=task_id,
                iteration_id=iteration_id,
                call_type="wording_generation",
                provider=self._adapter.provider,
                model_name=self._adapter.model_name,
                request_payload=request_payload,
                response_payload=None,
                status="error",
                error_message=str(e),
                duration_ms=duration_ms,
            )

            raise LlmGenerationError(
                "Не удалось сгенерировать формулировку задания.",
                task_id=task_id,
            ) from e

    def _build_prompt(
            self,
            task_type: int,
            subtype: str,
            params: dict[str, Any],
            target_param: str,
            reference_answer: int,
            previous_feedbacks: Optional[list[str]] = None,
            previous_wording: Optional[str] = None,
    ) -> str:
        """Формирует промпт для LLM из декларативных шаблонов."""

        display_params = {
            k: v for k, v in params.items()
            if not k.startswith("_")
            and k not in ("task_type", "subtype", "difficulty", "topic", "units", target_param)
        }
        params_text = "\n".join(f"  - {k}: {v}" for k, v in display_params.items())

        prompt = render(
            load_prompt("wording_generator.tmpl"),
            task_type=task_type,
            subtype=subtype,
            examples=_load_examples(task_type, subtype),
            formalism=load_prompt(f"task{task_type}/formalism.txt"),
            params_text=params_text,
            target_param=target_param,
            reference_answer=reference_answer,
        )

        if previous_feedbacks:
            history_lines = "\n".join(
                f"— Итерация {idx}: {fb}"
                for idx, fb in enumerate(previous_feedbacks, start=1)
            )
            prompt += render(
                load_prompt("wording_generator_retry.tmpl"),
                history_lines=history_lines,
            )
            if previous_wording:
                prompt += render(
                    load_prompt("wording_generator_retry_with_wording.tmpl"),
                    previous_wording=previous_wording,
                )
            else:
                prompt += "Пожалуйста, исправь формулировку с учётом всех замечаний.\n"

        return prompt


def _load_examples(task_type: int, subtype: str) -> str:
    """Возвращает few-shot пример под (task_type, subtype) или пустую строку."""

    return load_prompt(f"task{task_type}/few_shot/{subtype}.txt")
