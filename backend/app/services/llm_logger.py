"""
Логирование вызовов LLM в базу данных и Prometheus-метрики.

Функция log_llm_call создаёт запись в таблице llm_calls и
инкрементирует счётчик llm_calls_total.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.metrics import llm_calls_total
from backend.app.models.llm_call import LlmCall

logger = logging.getLogger(__name__)


def _estimate_cost_rub(
        provider: str,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
) -> Optional[float]:
    """
    Оценивает стоимость вызова LLM в рублях по тарифам из settings.

    Возвращает None, если:
    - токены не известны;
    - провайдер не поддерживается;
    - тарифы для провайдера не заданы (оба нулевые).
    """

    if not prompt_tokens and not completion_tokens:
        return None
    if provider == "yandexgpt":
        price_prompt = settings.yandexgpt_price_rub_per_1k_prompt
        price_completion = settings.yandexgpt_price_rub_per_1k_completion
    elif provider == "gigachat":
        price_prompt = settings.gigachat_price_rub_per_1k_prompt
        price_completion = settings.gigachat_price_rub_per_1k_completion
    else:
        return None
    if price_prompt == 0 and price_completion == 0:
        return None
    cost = (
        (prompt_tokens or 0) * price_prompt
        + (completion_tokens or 0) * price_completion
    ) / 1000.0
    return round(cost, 6)


async def log_llm_call(
        session: AsyncSession,
        *,
        task_id: UUID,
        iteration_id: UUID,
        call_type: str,
        provider: str,
        model_name: str,
        request_payload: Optional[dict] = None,
        response_payload: Optional[dict] = None,
        status: str,
        error_message: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        estimated_cost_rub: Optional[float] = None,
        duration_ms: Optional[int] = None,
) -> LlmCall:
    """
    Создаёт запись LlmCall в рамках предоставленной сессии.
    Запись добавляется и flush'ится, но не коммитится -
    коммит управляется вызывающим кодом.
    """

    if estimated_cost_rub is None:
        estimated_cost_rub = _estimate_cost_rub(
            provider, prompt_tokens, completion_tokens,
        )

    call = LlmCall(
        task_id=task_id,
        iteration_id=iteration_id,
        call_type=call_type,
        provider=provider,
        model_name=model_name,
        request_payload=request_payload,
        response_payload=response_payload,
        status=status,
        error_message=error_message,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_rub=estimated_cost_rub,
        duration_ms=duration_ms,
    )
    session.add(call)
    await session.flush()

    llm_calls_total.labels(
        call_type=call_type,
        provider=provider,
        status=status,
    ).inc()

    return call
