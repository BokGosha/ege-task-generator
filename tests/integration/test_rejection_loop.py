"""
Интеграционные тесты цикла отклонения формулировки (rejection loop).
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from httpx import AsyncClient

from backend.app.services.wording_validator import ValidationResult

pytestmark = [pytest.mark.asyncio]


def _patch_numeric_check_passes():
    """Отключает детерминированную числовую проверку — она имеет свои unit-тесты."""

    return patch(
        "backend.app.services.task_orchestrator.find_missing_params",
        return_value=[],
    )


def _make_rejected_result(message: str = "Проблема") -> ValidationResult:
    """Создаёт отклонённый ValidationResult."""

    return ValidationResult(
        clarity_pass=False, clarity_message=message,
        unambiguity_pass=True, unambiguity_message=None,
        consistency_pass=True, consistency_message=None,
        answer_format_pass=True, answer_format_message=None,
        language_correctness_pass=True, language_correctness_message=None,
    )


def _make_accepted_result() -> ValidationResult:
    """Создаёт принятый ValidationResult."""

    return ValidationResult(
        clarity_pass=True, clarity_message="OK",
        unambiguity_pass=True, unambiguity_message="OK",
        consistency_pass=True, consistency_message="OK",
        answer_format_pass=True, answer_format_message="OK",
        language_correctness_pass=True, language_correctness_message="OK",
    )


class TestAllIterationsRejected:
    """Все 3 итерации отклонены → status=rejected."""

    async def test_status_rejected_after_max_iterations(self, client: AsyncClient) -> None:
        """При всех отклонённых итерациях задание имеет status=rejected и 3 итерации."""

        with patch(
            "backend.app.services.wording_validator.WordingValidator.validate",
            new_callable=AsyncMock,
            return_value=_make_rejected_result(),
        ):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "rejected"
        assert len(body["iterations"]) == 3

    async def test_iterations_list_has_three_entries(self, client: AsyncClient) -> None:
        """При 3 отклонениях все итерации имеют status=rejected."""

        with patch(
            "backend.app.services.wording_validator.WordingValidator.validate",
            new_callable=AsyncMock,
            return_value=_make_rejected_result(),
        ):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 11},
            )

        body = resp.json()
        assert len(body["iterations"]) == 3
        for it in body["iterations"]:
            assert it["status"] == "rejected"


class TestAcceptOnSecondIteration:
    """Принимается на 2-й итерации → status=accepted."""

    async def test_accepted_on_second_attempt(self, client: AsyncClient) -> None:
        """Первая итерация rejected, вторая accepted — итого 2 итерации."""

        validate_mock = AsyncMock(
            side_effect=[_make_rejected_result(), _make_accepted_result()],
        )
        with _patch_numeric_check_passes(), patch(
            "backend.app.services.wording_validator.WordingValidator.validate",
            validate_mock,
        ):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7},
            )

        body = resp.json()
        assert body["status"] == "accepted"
        assert len(body["iterations"]) == 2


class TestFeedbackPropagation:
    """Feedback от валидатора передаётся в генератор при следующей итерации."""

    async def test_feedback_passed_to_generator(self, client: AsyncClient) -> None:
        """Второй вызов WordingGenerator.generate получает previous_feedback с текстом ошибки."""

        generate_mock = AsyncMock(return_value="Текст задания")
        validate_mock = AsyncMock(
            side_effect=[
                _make_rejected_result("Формулировка неясна"),
                _make_accepted_result(),
            ],
        )

        with _patch_numeric_check_passes(), patch(
            "backend.app.services.wording_generator.WordingGenerator.generate",
            generate_mock,
        ), patch(
            "backend.app.services.wording_validator.WordingValidator.validate",
            validate_mock,
        ):
            await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7},
            )

        first_call_kwargs = generate_mock.call_args_list[0].kwargs
        assert first_call_kwargs.get("previous_feedbacks") is None
        assert first_call_kwargs.get("previous_wording") is None

        second_call_kwargs = generate_mock.call_args_list[1].kwargs
        feedbacks = second_call_kwargs["previous_feedbacks"]
        assert feedbacks is not None and len(feedbacks) == 1
        assert "clarity" in feedbacks[0]
        assert second_call_kwargs["previous_wording"] == "Текст задания"
