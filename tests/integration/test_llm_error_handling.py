"""
Интеграционные тесты обработки ошибок LLM в конвейере генерации.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from httpx import AsyncClient

from backend.app.core.exceptions import (
    LlmTimeoutError,
    LlmGenerationError,
    LlmValidationError,
)

pytestmark = [pytest.mark.asyncio]


class TestLlmTimeoutOnGeneration:
    """Таймаут при генерации формулировки → 504."""

    async def test_returns_504_with_error_body(self, client: AsyncClient) -> None:
        """LlmTimeoutError на этапе генерации формулировки возвращает HTTP 504 с кодом LLM_TIMEOUT."""

        with patch(
            "backend.app.services.wording_generator.WordingGenerator.generate",
            new_callable=AsyncMock,
            side_effect=LlmTimeoutError("Таймаут генерации", task_id=None),
        ):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7},
            )

        assert resp.status_code == 504
        body = resp.json()
        assert body["error"]["code"] == "LLM_TIMEOUT"

    async def test_task_persisted_with_error_status(self, client: AsyncClient, db_session) -> None:
        """При таймауте задание сохраняется в БД и task_id возвращается в теле ошибки."""

        with patch(
            "backend.app.services.wording_generator.WordingGenerator.generate",
            new_callable=AsyncMock,
            side_effect=LlmTimeoutError("Таймаут", task_id=None),
        ):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7},
            )

        assert resp.status_code == 504
        task_id = resp.json()["error"]["details"]["task_id"]
        assert task_id is not None


class TestLlmTimeoutOnValidation:
    """Таймаут при валидации формулировки → 504."""

    async def test_returns_504_on_validation_timeout(self, client: AsyncClient) -> None:
        """LlmTimeoutError на этапе валидации возвращает HTTP 504."""

        with patch(
            "backend.app.services.wording_validator.WordingValidator.validate",
            new_callable=AsyncMock,
            side_effect=LlmTimeoutError("Таймаут валидации", task_id=None),
        ):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 11},
            )

        assert resp.status_code == 504
        body = resp.json()
        assert body["error"]["code"] == "LLM_TIMEOUT"


class TestLlmGenerationError:
    """Ошибка генерации формулировки → 500."""

    async def test_returns_500_on_generation_error(self, client: AsyncClient) -> None:
        """LlmGenerationError возвращает HTTP 500 с кодом LLM_GENERATION_FAILED."""

        with patch(
            "backend.app.services.wording_generator.WordingGenerator.generate",
            new_callable=AsyncMock,
            side_effect=LlmGenerationError("Сбой генерации", task_id=None),
        ):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7, "subtype": "image_size"},
            )

        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "LLM_GENERATION_FAILED"


class TestLlmValidationError:
    """Ошибка валидации формулировки → 500."""

    async def test_returns_500_on_validation_error(self, client: AsyncClient) -> None:
        """LlmValidationError возвращает HTTP 500 с кодом LLM_VALIDATION_FAILED."""

        with patch(
            "backend.app.services.wording_validator.WordingValidator.validate",
            new_callable=AsyncMock,
            side_effect=LlmValidationError("Ошибка валидации", task_id=None),
        ):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7},
            )

        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "LLM_VALIDATION_FAILED"
