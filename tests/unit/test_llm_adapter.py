"""
Unit-тесты LLM-адаптеров и защитного слоя _call_llm_with_guards.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from backend.app.core.config import settings
from backend.app.core.exceptions import LlmTimeoutError
from backend.app.services import llm_adapter as llm_module
from backend.app.services.llm_adapter import (
    BaseLlmAdapter,
    GigaChatAdapter,
    MockLlmAdapter,
    YandexGptAdapter,
    _call_llm_with_guards,
    get_llm_adapter,
)

pytestmark = [pytest.mark.asyncio]


class TestLlmAdapterFactory:
    """Фабрика get_llm_adapter возвращает корректный класс по имени провайдера."""

    def test_default_returns_mock(self) -> None:
        """get_llm_adapter() без аргумента возвращает MockLlmAdapter."""

        adapter = get_llm_adapter()
        assert isinstance(adapter, MockLlmAdapter)

    def test_explicit_mock_returns_mock(self) -> None:
        """Явное "mock" возвращает MockLlmAdapter."""

        adapter = get_llm_adapter("mock")
        assert isinstance(adapter, MockLlmAdapter)

    def test_unknown_provider_returns_mock(self) -> None:
        """Неизвестный провайдер возвращает MockLlmAdapter как fallback."""

        adapter = get_llm_adapter("unknown_provider")
        assert isinstance(adapter, MockLlmAdapter)

    def test_yandex_provider_returns_yandex_adapter(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_llm_adapter("yandexgpt") создаёт YandexGptAdapter."""

        monkeypatch.setattr(
            YandexGptAdapter, "__init__", lambda self: setattr(self, "model_name", "yandexgpt") or None,
        )
        adapter = get_llm_adapter("yandexgpt")
        assert isinstance(adapter, YandexGptAdapter)

    def test_gigachat_provider_returns_gigachat_adapter(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_llm_adapter("gigachat") создаёт GigaChatAdapter."""

        adapter = get_llm_adapter("gigachat")
        assert isinstance(adapter, GigaChatAdapter)


class TestMockLlmAdapter:
    """MockLlmAdapter — детерминированный адаптер для тестов."""

    async def test_generate_text_returns_prefixed_string(self) -> None:
        """generate_text возвращает строку с префиксом [MOCK]."""

        adapter = MockLlmAdapter()
        text = await adapter.generate_text("some prompt")
        assert "[MOCK]" in text

    async def test_generate_text_sets_token_usage(self) -> None:
        """После вызова last_token_usage содержит prompt_tokens и completion_tokens."""

        adapter = MockLlmAdapter()
        await adapter.generate_text("prompt")
        assert adapter.last_token_usage is not None
        assert "prompt_tokens" in adapter.last_token_usage
        assert "completion_tokens" in adapter.last_token_usage

    async def test_generate_json_follows_schema(self) -> None:
        """generate_json возвращает dict, удовлетворяющий переданной схеме.

        Boolean → True, string → непустая строка — чтобы результат
        проходил downstream-валидаторы (например, WordingValidator).
        """

        adapter = MockLlmAdapter()
        schema = {
            "type": "object",
            "required": ["passed", "message"],
            "properties": {
                "passed": {"type": "boolean"},
                "message": {"type": "string"},
            },
        }
        result = await adapter.generate_json("prompt", schema)
        assert isinstance(result, dict)
        assert result["passed"] is True
        assert isinstance(result["message"], str) and result["message"]

    def test_is_subclass_of_base(self) -> None:
        """MockLlmAdapter является наследником BaseLlmAdapter."""

        assert issubclass(MockLlmAdapter, BaseLlmAdapter)


class TestCallLlmWithGuardsTimeout:
    """Поведение таймаута в _call_llm_with_guards."""

    async def test_success_on_first_attempt(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Операция, возвращающая результат сразу, вызывается один раз."""

        monkeypatch.setattr(settings, "llm_timeout_seconds", 5.0)
        monkeypatch.setattr(settings, "llm_retry_attempts", 3)
        monkeypatch.setattr(settings, "llm_retry_initial_delay", 0.001)

        call_count = {"n": 0}

        async def op():
            call_count["n"] += 1
            return "ok"

        result = await _call_llm_with_guards(op, provider="test", call_type="text")

        assert result == "ok"
        assert call_count["n"] == 1

    async def test_timeout_raises_llm_timeout_error(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Операция, превышающая llm_timeout_seconds, вызывает LlmTimeoutError."""

        monkeypatch.setattr(settings, "llm_timeout_seconds", 0.05)
        monkeypatch.setattr(settings, "llm_retry_attempts", 3)
        monkeypatch.setattr(settings, "llm_retry_initial_delay", 0.001)

        async def slow_op():
            await asyncio.sleep(5)

        with pytest.raises(LlmTimeoutError):
            await _call_llm_with_guards(slow_op, provider="test", call_type="text")

    async def test_timeout_is_not_retried(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Таймаут не запускает retry — операция вызывается ровно один раз."""

        monkeypatch.setattr(settings, "llm_timeout_seconds", 0.05)
        monkeypatch.setattr(settings, "llm_retry_attempts", 5)
        monkeypatch.setattr(settings, "llm_retry_initial_delay", 0.001)

        call_count = {"n": 0}

        async def slow_op():
            call_count["n"] += 1
            await asyncio.sleep(5)

        with pytest.raises(LlmTimeoutError):
            await _call_llm_with_guards(slow_op, provider="test", call_type="text")

        assert call_count["n"] == 1


class TestCallLlmWithGuardsRetry:
    """Retry-поведение при транспортных сбоях."""

    async def test_transient_failure_then_success(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Операция падает 2 раза, на 3-й возвращает значение — результат получен."""

        monkeypatch.setattr(settings, "llm_timeout_seconds", 5.0)
        monkeypatch.setattr(settings, "llm_retry_attempts", 3)
        monkeypatch.setattr(settings, "llm_retry_initial_delay", 0.001)

        call_count = {"n": 0}

        async def flaky_op():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError(f"attempt {call_count['n']}")
            return "success"

        result = await _call_llm_with_guards(
            flaky_op, provider="test", call_type="text",
        )

        assert result == "success"
        assert call_count["n"] == 3

    async def test_exhausts_retries_and_reraises(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Все попытки провалились — последнее исключение пробрасывается."""

        monkeypatch.setattr(settings, "llm_timeout_seconds", 5.0)
        monkeypatch.setattr(settings, "llm_retry_attempts", 3)
        monkeypatch.setattr(settings, "llm_retry_initial_delay", 0.001)

        call_count = {"n": 0}

        async def always_fails():
            call_count["n"] += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await _call_llm_with_guards(
                always_fails, provider="test", call_type="text",
            )

        assert call_count["n"] == 3


class TestCallLlmWithGuardsSemaphore:
    """Семафор ограничивает параллельные LLM-вызовы."""

    async def test_semaphore_limits_concurrency(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """При семафоре на 2 слота одновременно выполняется не более 2 операций из 8."""

        monkeypatch.setattr(settings, "llm_timeout_seconds", 5.0)
        monkeypatch.setattr(settings, "llm_retry_attempts", 1)
        monkeypatch.setattr(settings, "llm_retry_initial_delay", 0.001)
        monkeypatch.setattr(llm_module, "_llm_semaphore", asyncio.Semaphore(2))

        state = {"current": 0, "max": 0}
        lock = asyncio.Lock()

        async def tracked_op():
            async with lock:
                state["current"] += 1
                state["max"] = max(state["max"], state["current"])
            await asyncio.sleep(0.05)
            async with lock:
                state["current"] -= 1
            return "ok"

        results = await asyncio.gather(*[
            _call_llm_with_guards(tracked_op, provider="t", call_type="text")
            for _ in range(8)
        ])

        assert all(r == "ok" for r in results)
        assert state["max"] <= 2, f"Параллельных вызовов: {state['max']}, ожидалось ≤2"
