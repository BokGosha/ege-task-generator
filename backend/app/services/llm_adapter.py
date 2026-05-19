"""
Адаптеры LLM-провайдеров (YandexGPT, GigaChat, Mock).

Определяет абстрактный интерфейс BaseLlmAdapter и конкретные реализации
для каждого поддерживаемого провайдера. Фабричная функция get_llm_adapter
создаёт экземпляр по имени провайдера из конфигурации.

Модуль содержит защиту от перегрузки внешних LLM:
- глобальный asyncio.Semaphore ограничивает число одновременных вызовов
  на один процесс uvicorn;
- каждый сетевой вызов обёрнут в asyncio.wait_for с таймаутом;
- tenacity повторяет транспортные сбои с экспоненциальным бэкоффом,
  не ретрая LlmTimeoutError и отмену корутины.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Optional, TypeVar

from tenacity import (
    AsyncRetrying,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.app.core.config import settings
from backend.app.core.exceptions import LlmTimeoutError

logger = logging.getLogger(__name__)

_llm_semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

T = TypeVar("T")


def _extract_yandex_usage(result: Any) -> Optional[dict[str, int]]:
    """
    Извлекает prompt_tokens/completion_tokens из результата yandex-ai-studio-sdk.

    У результата run() есть атрибут usage с полями input_text_tokens,
    completion_tokens, total_tokens (имена могут отличаться по версиям SDK,
    поэтому чтение защитное).
    """

    usage = getattr(result, "usage", None)
    if usage is None:
        return None
    prompt_tokens = (
        getattr(usage, "input_text_tokens", None)
        or getattr(usage, "prompt_tokens", None)
    )
    completion_tokens = getattr(usage, "completion_tokens", None)
    if prompt_tokens is None and completion_tokens is None:
        return None
    return {
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
    }


async def _call_llm_with_guards(
        operation: Callable[[], Awaitable[T]],
        *,
        provider: str,
        call_type: str,
) -> T:
    """
    Выполняет сетевой вызов LLM с защитой от перегрузки.

    Порядок операций: семафор → retry с бэкоффом → таймаут на каждую попытку.
    Таймаут поднимает ``LlmTimeoutError`` и НЕ ретраится (один таймаут обычно
    означает, что провайдер деградирует и повторы только ухудшат ситуацию).
    Прочие исключения ретраятся ``llm_retry_attempts`` раз.
    """

    async with _llm_semaphore:
        async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.llm_retry_attempts),
                wait=wait_exponential(
                    multiplier=settings.llm_retry_initial_delay,
                    max=10,
                ),
                retry=retry_if_not_exception_type(
                    (LlmTimeoutError, asyncio.CancelledError),
                ),
                reraise=True,
        ):
            with attempt:
                attempt_num = attempt.retry_state.attempt_number
                if attempt_num > 1:
                    logger.warning(
                        "Повторная попытка LLM-вызова provider=%s call=%s attempt=%d",
                        provider, call_type, attempt_num,
                    )
                try:
                    return await asyncio.wait_for(
                        operation(),
                        timeout=settings.llm_timeout_seconds,
                    )
                except asyncio.TimeoutError as exc:
                    logger.error(
                        "Таймаут LLM-вызова provider=%s call=%s timeout=%.1fs",
                        provider, call_type, settings.llm_timeout_seconds,
                    )
                    raise LlmTimeoutError(
                        f"Превышен таймаут ожидания ответа от LLM ({provider}).",
                    ) from exc


class BaseLlmAdapter(ABC):
    """Абстрактный интерфейс LLM-адаптера."""

    provider: str
    model_name: str
    last_token_usage: dict[str, int] | None = None

    @abstractmethod
    async def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict:
        """Генерация структурированного JSON-ответа."""
        ...

    @abstractmethod
    async def generate_text(self, prompt: str) -> str:
        """Генерация свободного текста."""
        ...


class YandexGptAdapter(BaseLlmAdapter):
    """
    Адаптер для YandexGPT через yandex-ai-studio-sdk.

    Использует модель yandexgpt для генерации текста и модель yandexgpt/rc
    с response_format для структурированного JSON-вывода.
    """

    provider = "yandexgpt"

    def __init__(self) -> None:
        from yandex_ai_studio_sdk import AsyncAIStudio

        self.model_name = "yandexgpt"
        self.sdk = AsyncAIStudio(
            folder_id=settings.yandexgpt_folder_id,
            auth=settings.yandexgpt_api_key,
        )

    async def generate_text(self, prompt: str) -> str:
        """Генерирует свободный текст через YandexGPT (temperature=0.5)."""

        async def _do_call() -> tuple[str, Optional[dict[str, int]]]:
            model = self.sdk.models.completions("yandexgpt")
            model = model.configure(temperature=0.5)
            result = await model.run([
                {"role": "user", "text": prompt},
            ])
            return result[0].text, _extract_yandex_usage(result)

        text, usage = await _call_llm_with_guards(
            _do_call, provider=self.provider, call_type="text",
        )
        self.last_token_usage = usage
        return text

    async def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict:
        """Генерирует структурированный JSON через YandexGPT RC с json_schema."""

        async def _do_call() -> tuple[str, Optional[dict[str, int]]]:
            model = self.sdk.models.completions("yandexgpt", model_version="rc")
            model = model.configure(temperature=0.3, response_format={"json_schema": schema})
            result = await model.run([
                {"role": "user", "text": prompt},
            ])
            return result[0].text, _extract_yandex_usage(result)

        raw_text, usage = await _call_llm_with_guards(
            _do_call, provider=self.provider, call_type="json",
        )
        self.last_token_usage = usage
        return json.loads(raw_text)


class GigaChatAdapter(BaseLlmAdapter):
    """
    Адаптер для GigaChat (Сбер).

    Модель и температура задаются в конструкторе: старшие модели
    (Pro/Max) работают строже и принципиальнее, что критично для
    роли LLM-валидатора. Для JSON-вывода дополняет промпт инструкцией
    и схемой, затем извлекает JSON из markdown-блока в ответе.
    """

    provider = "gigachat"

    def __init__(
            self,
            model: str | None = None,
            temperature: float | None = None,
    ) -> None:
        self.model_name = model or "GigaChat"
        self._temperature = temperature
        self._credentials = settings.gigachat_credentials
        self._scope = settings.gigachat_scope

    async def generate_text(self, prompt: str) -> str:
        """Генерирует свободный текст через GigaChat API."""

        text, usage = await self._chat(prompt)
        self.last_token_usage = usage
        return text

    async def _chat(self, prompt: str) -> tuple[str, Optional[dict[str, int]]]:
        """Один вызов GigaChat, возвращает (текст, usage) из response.usage."""

        from gigachat import GigaChat
        from gigachat.models import Chat, Messages, MessagesRole

        chat_payload = Chat(
            model=self.model_name,
            messages=[Messages(role=MessagesRole.USER, content=prompt)],
            temperature=self._temperature,
        )

        async def _do_call() -> tuple[str, Optional[dict[str, int]]]:
            async with GigaChat(
                    credentials=self._credentials,
                    scope=self._scope,
                    verify_ssl_certs=False,
            ) as client:
                response = await client.achat(chat_payload)
                content = response.choices[0].message.content
                usage_obj = getattr(response, "usage", None)
                usage: Optional[dict[str, int]] = None
                if usage_obj is not None:
                    prompt_tokens = getattr(usage_obj, "prompt_tokens", None)
                    completion_tokens = getattr(usage_obj, "completion_tokens", None)
                    if prompt_tokens is not None or completion_tokens is not None:
                        usage = {
                            "prompt_tokens": int(prompt_tokens or 0),
                            "completion_tokens": int(completion_tokens or 0),
                        }
                return content, usage

        return await _call_llm_with_guards(
            _do_call, provider=self.provider, call_type="text",
        )

    async def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict:
        """Генерирует JSON через GigaChat, дополняя промпт схемой и извлекая JSON из ответа."""

        json_prompt = (
            f"{prompt}\n\n"
            "ВАЖНО: Верни ответ СТРОГО в формате JSON, без дополнительного текста.\n"
            f"Схема JSON:\n```json\n{json.dumps(schema, indent=2, ensure_ascii=False)}\n```"
        )
        text, usage = await self._chat(json_prompt)
        self.last_token_usage = usage
        raw = text
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            parts = raw.split("```")
            if len(parts) >= 3:
                raw = parts[1].strip()
        return json.loads(raw)


class MockLlmAdapter(BaseLlmAdapter):
    """
    Мок-адаптер для тестирования.

    Возвращает детерминированные ответы без обращения к внешним API.
    Используется при llm_*_provider = "mock" в конфигурации.
    """

    provider = "mock"
    model_name = "mock"

    async def generate_text(self, prompt: str) -> str:
        """Возвращает строку-заглушку с префиксом [MOCK]."""

        import re

        self.last_token_usage = {
            "prompt_tokens": 10,
            "completion_tokens": 20,
        }
        numbers = re.findall(r"\d+", prompt)
        numbers_block = " ".join(numbers)
        return f"[MOCK] {prompt[:120]} | numbers: {numbers_block}"

    async def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict:
        """Возвращает детерминированный объект, удовлетворяющий схеме.

        Для boolean-полей возвращает True (accepted-исход), для string —
        осмысленный mock-текст, чтобы пройти проверки длины и содержания
        в валидаторах.
        """

        self.last_token_usage = {
            "prompt_tokens": 10,
            "completion_tokens": 20,
        }
        return self._build_from_schema(schema)

    @classmethod
    def _build_from_schema(cls, schema: dict[str, Any]) -> Any:
        """Рекурсивно строит значение, соответствующее JSON-схеме."""

        if not isinstance(schema, dict):
            return None

        schema_type = schema.get("type")
        if schema_type == "object" or "properties" in schema:
            properties = schema.get("properties", {})
            required = schema.get("required") or list(properties.keys())
            return {
                field: cls._build_from_schema(properties.get(field, {}))
                for field in required
            }
        if schema_type == "array":
            return []
        if schema_type == "boolean":
            return True
        if schema_type in ("integer", "number"):
            return 0
        if schema_type == "string":
            return "[MOCK] Формулировка соответствует требованиям."
        return None


def get_llm_adapter(
        provider: str | None = None,
        purpose: str = "generation",
) -> BaseLlmAdapter:
    """Фабрика LLM-адаптеров."""

    if provider == "yandexgpt":
        return YandexGptAdapter()
    if provider == "gigachat":
        if purpose == "validation":
            return GigaChatAdapter(
                model=settings.gigachat_validation_model,
                temperature=settings.gigachat_validation_temperature,
            )
        return GigaChatAdapter(
            model=settings.gigachat_generation_model,
            temperature=settings.gigachat_generation_temperature,
        )
    return MockLlmAdapter()
