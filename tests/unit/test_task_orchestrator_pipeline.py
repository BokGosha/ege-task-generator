"""
Unit-тесты оркестратора конвейера TaskOrchestrator._run_pipeline.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.app.core.exceptions import (
    LlmGenerationError,
    LlmTimeoutError,
    LlmValidationError,
)
from backend.app.services.task_orchestrator import TaskOrchestrator, MAX_LLM_ITERATIONS
from backend.app.services.wording_validator import ValidationResult

pytestmark = [pytest.mark.asyncio]


def _accepted_result() -> ValidationResult:
    return ValidationResult(
        clarity_pass=True, clarity_message="OK",
        unambiguity_pass=True, unambiguity_message="OK",
        consistency_pass=True, consistency_message="OK",
        answer_format_pass=True, answer_format_message="OK",
        language_correctness_pass=True, language_correctness_message="OK",
    )


def _rejected_result(msg: str = "Неясно") -> ValidationResult:
    return ValidationResult(
        clarity_pass=False, clarity_message=msg,
        unambiguity_pass=True, unambiguity_message=None,
        consistency_pass=True, consistency_message=None,
        answer_format_pass=True, answer_format_message=None,
        language_correctness_pass=True, language_correctness_message=None,
    )


def _mock_session():
    """Создаёт мок AsyncSession с работающими add/flush/commit."""

    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


def _patch_param_generator():
    """Патч ParamGeneratorService.generate → успешный результат."""

    return patch(
        "backend.app.services.task_orchestrator.ParamGeneratorService.generate",
        new_callable=AsyncMock,
        return_value=(
            {"subtype": "image_size", "width": 1024, "height": 768, "color_depth": 24},
            "image_size",
            2359296,
            "image_size",
        ),
    )


def _patch_get_task_by_id():
    """Патч get_task_by_id → mock-ответ."""

    mock_response = MagicMock()
    mock_response.status = "accepted"
    return patch(
        "backend.app.services.task_orchestrator.get_task_by_id",
        new_callable=AsyncMock,
        return_value=mock_response,
    )


class TestFailureStageGeneration:
    """Проверяет failure_stage='generation' при ошибке генерации формулировки."""

    async def test_timeout_sets_failure_stage_generation(self) -> None:
        """LlmTimeoutError при генерации устанавливает failure_stage='generation'."""

        session = _mock_session()
        orchestrator = TaskOrchestrator()

        with _patch_param_generator(), patch(
            "backend.app.services.task_orchestrator.WordingGenerator.generate",
            new_callable=AsyncMock,
            side_effect=LlmTimeoutError("Таймаут", task_id=None),
        ):
            with pytest.raises(LlmTimeoutError):
                await orchestrator.execute(session=session, task_type=7)

        added_objects = [call.args[0] for call in session.add.call_args_list]
        iterations = [
            obj for obj in added_objects
            if hasattr(obj, "failure_stage") and obj.failure_stage is not None
        ]
        assert len(iterations) >= 1
        assert iterations[0].failure_stage == "generation"
        assert "Таймаут" in iterations[0].failure_reason

    async def test_generation_error_sets_failure_stage(self) -> None:
        """LlmGenerationError устанавливает failure_stage='generation'."""

        session = _mock_session()
        orchestrator = TaskOrchestrator()

        with _patch_param_generator(), patch(
            "backend.app.services.task_orchestrator.WordingGenerator.generate",
            new_callable=AsyncMock,
            side_effect=LlmGenerationError("Сбой", task_id=None),
        ):
            with pytest.raises(LlmGenerationError):
                await orchestrator.execute(session=session, task_type=7)

        added_objects = [call.args[0] for call in session.add.call_args_list]
        iterations = [
            obj for obj in added_objects
            if hasattr(obj, "failure_stage") and obj.failure_stage is not None
        ]
        assert len(iterations) >= 1
        assert iterations[0].failure_stage == "generation"


class TestFailureStageValidation:
    """Проверяет failure_stage='validation' при ошибке валидации."""

    async def test_timeout_sets_failure_stage_validation(self) -> None:
        """LlmTimeoutError при валидации устанавливает failure_stage='validation'."""

        session = _mock_session()
        orchestrator = TaskOrchestrator()

        with _patch_param_generator(), patch(
            "backend.app.services.task_orchestrator.WordingGenerator.generate",
            new_callable=AsyncMock,
            return_value="Текст задания",
        ), patch(
            "backend.app.services.task_orchestrator.WordingValidator.validate",
            new_callable=AsyncMock,
            side_effect=LlmTimeoutError("Таймаут валидации", task_id=None),
        ):
            with pytest.raises(LlmTimeoutError):
                await orchestrator.execute(session=session, task_type=7)

        added_objects = [call.args[0] for call in session.add.call_args_list]
        iterations = [
            obj for obj in added_objects
            if hasattr(obj, "failure_stage") and obj.failure_stage is not None
        ]
        assert len(iterations) >= 1
        assert iterations[0].failure_stage == "validation"
        assert "валидации" in iterations[0].failure_reason.lower()

    async def test_validation_error_sets_failure_stage(self) -> None:
        """LlmValidationError устанавливает failure_stage='validation'."""

        session = _mock_session()
        orchestrator = TaskOrchestrator()

        with _patch_param_generator(), patch(
            "backend.app.services.task_orchestrator.WordingGenerator.generate",
            new_callable=AsyncMock,
            return_value="Текст задания",
        ), patch(
            "backend.app.services.task_orchestrator.WordingValidator.validate",
            new_callable=AsyncMock,
            side_effect=LlmValidationError("Ошибка", task_id=None),
        ):
            with pytest.raises(LlmValidationError):
                await orchestrator.execute(session=session, task_type=7)

        added_objects = [call.args[0] for call in session.add.call_args_list]
        iterations = [
            obj for obj in added_objects
            if hasattr(obj, "failure_stage") and obj.failure_stage is not None
        ]
        assert len(iterations) >= 1
        assert iterations[0].failure_stage == "validation"


class TestSelfCorrection:
    """Проверяет передачу feedback из валидатора в следующую итерацию генератора."""

    async def test_feedback_propagated_across_iterations(self) -> None:
        """feedback_text() от rejected-итерации передаётся как previous_feedback во вторую."""

        session = _mock_session()
        orchestrator = TaskOrchestrator()

        gen_mock = AsyncMock(side_effect=[
            "Текст задания",
            "Картинка 1024 на 768 с глубиной 24 бита.",
        ])
        val_mock = AsyncMock(side_effect=[
            _rejected_result("Условие неясно"),
            _accepted_result(),
        ])

        with _patch_param_generator(), _patch_get_task_by_id(), patch(
            "backend.app.services.task_orchestrator.WordingGenerator.generate",
            gen_mock,
        ), patch(
            "backend.app.services.task_orchestrator.WordingValidator.validate",
            val_mock,
        ):
            await orchestrator.execute(session=session, task_type=7)

        assert gen_mock.call_args_list[0].kwargs.get("previous_feedbacks") is None
        assert gen_mock.call_args_list[0].kwargs.get("previous_wording") is None

        second_feedbacks = gen_mock.call_args_list[1].kwargs["previous_feedbacks"]
        assert second_feedbacks is not None
        assert len(second_feedbacks) == 1
        assert "clarity" in second_feedbacks[0]
        assert "Условие неясно" in second_feedbacks[0]
        assert gen_mock.call_args_list[1].kwargs["previous_wording"] == "Текст задания"

    async def test_numeric_check_overrides_llm_accept(self) -> None:
        """LLM-валидатор accept, но в тексте нет параметров → итерация отклоняется."""

        session = _mock_session()
        orchestrator = TaskOrchestrator()

        # На 1-й итерации wording без чисел, на 2-й — с числами параметров.
        gen_mock = AsyncMock(side_effect=[
            "Текст без чисел вообще.",
            "Картинка 1024 на 768 с глубиной 24 бита.",
        ])
        val_mock = AsyncMock(return_value=_accepted_result())

        with _patch_param_generator(), _patch_get_task_by_id(), patch(
            "backend.app.services.task_orchestrator.WordingGenerator.generate",
            gen_mock,
        ), patch(
            "backend.app.services.task_orchestrator.WordingValidator.validate",
            val_mock,
        ):
            await orchestrator.execute(session=session, task_type=7)

        assert gen_mock.call_count == 2
        second_feedbacks = gen_mock.call_args_list[1].kwargs["previous_feedbacks"]
        assert second_feedbacks is not None
        assert "numeric_match" in second_feedbacks[0]

    async def test_accepted_first_iteration_no_feedback(self) -> None:
        """При accept на 1-й итерации generate вызывается один раз без feedback."""

        session = _mock_session()
        orchestrator = TaskOrchestrator()

        gen_mock = AsyncMock(return_value="Картинка 1024 на 768 с глубиной 24 бита.")
        val_mock = AsyncMock(return_value=_accepted_result())

        with _patch_param_generator(), _patch_get_task_by_id(), patch(
            "backend.app.services.task_orchestrator.WordingGenerator.generate",
            gen_mock,
        ), patch(
            "backend.app.services.task_orchestrator.WordingValidator.validate",
            val_mock,
        ):
            await orchestrator.execute(session=session, task_type=7)

        assert gen_mock.call_count == 1
        assert gen_mock.call_args_list[0].kwargs.get("previous_feedbacks") is None
        assert gen_mock.call_args_list[0].kwargs.get("previous_wording") is None


class TestIterationCount:
    """Проверяет количество итераций в разных сценариях."""

    async def test_max_iterations_on_all_rejected(self) -> None:
        """При всех rejected валидатор вызывается ровно MAX_LLM_ITERATIONS раз."""

        session = _mock_session()
        orchestrator = TaskOrchestrator()

        val_mock = AsyncMock(return_value=_rejected_result())

        with _patch_param_generator(), _patch_get_task_by_id(), patch(
            "backend.app.services.task_orchestrator.WordingGenerator.generate",
            new_callable=AsyncMock,
            return_value="Текст",
        ), patch(
            "backend.app.services.task_orchestrator.WordingValidator.validate",
            val_mock,
        ):
            await orchestrator.execute(session=session, task_type=7)

        assert val_mock.call_count == MAX_LLM_ITERATIONS
