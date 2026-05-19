"""
Unit-тесты для WordingValidator и ValidationResult.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.app.services.wording_validator import (
    ValidationResult,
    WordingValidator,
)
from backend.app.core.exceptions import LlmTimeoutError, LlmValidationError


class TestValidationResultIsAccepted:
    """Проверяет логику is_accepted: True только при прохождении всех 5 критериев."""

    def test_all_true_means_accepted(self) -> None:
        """Все критерии True — формулировка принята."""

        result = ValidationResult(
            clarity_pass=True, clarity_message=None,
            unambiguity_pass=True, unambiguity_message=None,
            consistency_pass=True, consistency_message=None,
            answer_format_pass=True, answer_format_message=None,
            language_correctness_pass=True, language_correctness_message=None,
        )
        assert result.is_accepted is True
        assert result.verdict == "accepted"

    @pytest.mark.parametrize("failed_field", [
        "clarity_pass",
        "unambiguity_pass",
        "consistency_pass",
        "answer_format_pass",
        "language_correctness_pass",
    ])
    def test_single_false_means_rejected(self, failed_field: str) -> None:
        """Один любой критерий False — формулировка отклонена."""

        kwargs = {
            "clarity_pass": True, "clarity_message": None,
            "unambiguity_pass": True, "unambiguity_message": None,
            "consistency_pass": True, "consistency_message": None,
            "answer_format_pass": True, "answer_format_message": None,
            "language_correctness_pass": True, "language_correctness_message": None,
        }
        kwargs[failed_field] = False
        kwargs[failed_field.replace("_pass", "_message")] = "Проблема"
        result = ValidationResult(**kwargs)
        assert result.is_accepted is False
        assert result.verdict == "rejected"

    def test_multiple_failures(self) -> None:
        """Несколько непройденных критериев — is_accepted = False."""

        result = ValidationResult(
            clarity_pass=False, clarity_message="Неясно",
            unambiguity_pass=False, unambiguity_message="Неоднозначно",
            consistency_pass=True, consistency_message=None,
            answer_format_pass=True, answer_format_message=None,
            language_correctness_pass=True, language_correctness_message=None,
        )
        assert result.is_accepted is False


class TestValidationResultFeedback:
    """Проверяет формирование обратной связи для повторной генерации."""

    def test_failed_criteria_lists_only_failures(self) -> None:
        """failed_criteria возвращает только непройденные критерии."""

        result = ValidationResult(
            clarity_pass=False, clarity_message="Неясно",
            unambiguity_pass=True, unambiguity_message=None,
            consistency_pass=False, consistency_message="Противоречие",
            answer_format_pass=True, answer_format_message=None,
            language_correctness_pass=True, language_correctness_message=None,
        )
        failed = result.failed_criteria()
        assert len(failed) == 2
        assert ("clarity", "Неясно") in failed
        assert ("consistency", "Противоречие") in failed

    def test_feedback_text_empty_when_accepted(self) -> None:
        """При полном принятии feedback_text() возвращает пустую строку."""

        result = ValidationResult(
            clarity_pass=True, clarity_message=None,
            unambiguity_pass=True, unambiguity_message=None,
            consistency_pass=True, consistency_message=None,
            answer_format_pass=True, answer_format_message=None,
            language_correctness_pass=True, language_correctness_message=None,
        )
        assert result.feedback_text() == ""

    def test_feedback_text_contains_criteria_names(self) -> None:
        """Текст обратной связи содержит имена провалившихся критериев и их сообщения."""

        result = ValidationResult(
            clarity_pass=True, clarity_message=None,
            unambiguity_pass=False, unambiguity_message="Два ответа",
            consistency_pass=True, consistency_message=None,
            answer_format_pass=True, answer_format_message=None,
            language_correctness_pass=False, language_correctness_message="Ошибка",
        )
        feedback = result.feedback_text()
        assert "unambiguity" in feedback
        assert "language_correctness" in feedback
        assert "Два ответа" in feedback

    def test_diagnostic_message_when_accepted(self) -> None:
        """При успешной валидации diagnostic_message содержит «пригодна»."""

        result = ValidationResult(
            clarity_pass=True, clarity_message=None,
            unambiguity_pass=True, unambiguity_message=None,
            consistency_pass=True, consistency_message=None,
            answer_format_pass=True, answer_format_message=None,
            language_correctness_pass=True, language_correctness_message=None,
        )
        assert "пригодна" in result.diagnostic_message

    def test_diagnostic_message_when_rejected(self) -> None:
        """При отклонении diagnostic_message содержит перечень проблем."""

        result = ValidationResult(
            clarity_pass=False, clarity_message="Непонятно",
            unambiguity_pass=True, unambiguity_message=None,
            consistency_pass=True, consistency_message=None,
            answer_format_pass=True, answer_format_message=None,
            language_correctness_pass=True, language_correctness_message=None,
        )
        diag = result.diagnostic_message
        assert "не прошла проверку" in diag
        assert "clarity" in diag
        assert "Непонятно" in diag

    def test_failed_criteria_default_message_when_none(self) -> None:
        """Если message=None для непройденного критерия, используется дефолтный текст."""

        result = ValidationResult(
            clarity_pass=False, clarity_message=None,
            unambiguity_pass=True, unambiguity_message=None,
            consistency_pass=True, consistency_message=None,
            answer_format_pass=True, answer_format_message=None,
            language_correctness_pass=True, language_correctness_message=None,
        )
        failed = result.failed_criteria()
        assert failed[0] == ("clarity", "Критерий не пройден")


class TestParseResult:
    """Проверяет парсинг JSON-ответа от LLM в ValidationResult."""

    def _make_validator(self):
        adapter = MagicMock()
        return WordingValidator(adapter)

    def test_valid_full_response(self) -> None:
        """Полный валидный ответ корректно парсится в ValidationResult."""

        v = self._make_validator()
        raw = {
            "clarity_pass": True,
            "clarity_message": "Условие указывает размер в пикселях и бит на пиксель.",
            "unambiguity_pass": False, "unambiguity_message": "Два смысла",
            "consistency_pass": True,
            "consistency_message": "Числовые данные согласованы с единицами измерения.",
            "answer_format_pass": True,
            "answer_format_message": "Фраза «в байтах» задаёт целочисленный формат.",
            "language_correctness_pass": True,
            "language_correctness_message": "Термины употреблены корректно, ошибок нет в тексте.",
        }
        result = v._parse_result(raw)
        assert result.clarity_pass is True
        assert result.unambiguity_pass is False
        assert result.unambiguity_message == "Два смысла"

    def test_empty_justification_on_pass_inverts_to_false(self) -> None:
        """pass=true с пустым/шаблонным message трактуется как непройденный."""

        v = self._make_validator()
        raw = {
            "clarity_pass": True, "clarity_message": "OK",
            "unambiguity_pass": True, "unambiguity_message": "",
            "consistency_pass": True, "consistency_message": None,
            "answer_format_pass": True, "answer_format_message": "ошибок нет",
            "language_correctness_pass": True,
            "language_correctness_message": "Содержательное обоснование на 8+ символов.",
        }
        result = v._parse_result(raw)
        assert result.clarity_pass is False
        assert result.unambiguity_pass is False
        assert result.consistency_pass is False
        assert result.answer_format_pass is False
        assert result.language_correctness_pass is True

    def test_empty_response_raises_validation_error(self) -> None:
        """Пустой ответ без полей критериев трактуется как ошибка LLM."""

        v = self._make_validator()
        with pytest.raises(LlmValidationError):
            v._parse_result({})

    def test_non_dict_response_raises_validation_error(self) -> None:
        """Ответ неожиданного типа приводит к LlmValidationError."""

        v = self._make_validator()
        with pytest.raises(LlmValidationError):
            v._parse_result("not a dict")

    def test_partial_response_defaults_missing_to_false(self) -> None:
        """Fail-closed: отсутствующие поля считаются непройденными."""

        v = self._make_validator()
        raw = {
            "clarity_pass": False, "clarity_message": "Непонятно",
        }
        result = v._parse_result(raw)
        assert result.clarity_pass is False
        assert result.unambiguity_pass is False
        assert result.consistency_pass is False
        assert result.answer_format_pass is False
        assert result.language_correctness_pass is False
        assert result.unambiguity_message == "Критерий не оценён валидатором."

    def test_non_bool_pass_value_treated_as_false(self) -> None:
        """Любое значение кроме True (строки, None, 1) — считается False."""

        v = self._make_validator()
        meaningful = "Содержательное обоснование длиной не менее 8 символов."
        raw = {
            "clarity_pass": "true", "clarity_message": meaningful,
            "unambiguity_pass": 1, "unambiguity_message": meaningful,
            "consistency_pass": None, "consistency_message": meaningful,
            "answer_format_pass": True, "answer_format_message": meaningful,
            "language_correctness_pass": True, "language_correctness_message": meaningful,
        }
        result = v._parse_result(raw)
        assert result.clarity_pass is False
        assert result.unambiguity_pass is False
        assert result.consistency_pass is False
        assert result.answer_format_pass is True
        assert result.language_correctness_pass is True

    def test_wrapped_response_is_unwrapped(self) -> None:
        """Ответ, обёрнутый в {'result': {...}}, корректно разворачивается."""

        v = self._make_validator()
        meaningful = "Содержательное обоснование длиной не менее 8 символов."
        raw = {
            "result": {
                "clarity_pass": True, "clarity_message": meaningful,
                "unambiguity_pass": True, "unambiguity_message": meaningful,
                "consistency_pass": True, "consistency_message": meaningful,
                "answer_format_pass": True, "answer_format_message": meaningful,
                "language_correctness_pass": True,
                "language_correctness_message": meaningful,
            }
        }
        result = v._parse_result(raw)
        assert result.is_accepted is True


@pytest.mark.asyncio
class TestWordingValidatorErrors:
    """Проверяет обработку ошибок LLM в validate()."""

    async def test_timeout_raises_llm_timeout_error(self) -> None:
        """При таймауте адаптера поднимается LlmTimeoutError с task_id."""

        adapter = MagicMock()
        adapter.provider = "mock"
        adapter.model_name = "test"
        adapter.generate_json = AsyncMock(
            side_effect=LlmTimeoutError("timeout", task_id=None),
        )
        validator = WordingValidator(adapter)
        session = AsyncMock()
        task_id = uuid4()

        with pytest.raises(LlmTimeoutError) as exc_info:
            await validator.validate(
                session=session,
                task_id=task_id,
                iteration_id=uuid4(),
                task_type=7,
                subtype="image_size",
                wording="Текст задания",
                reference_answer=42,
            )
        assert exc_info.value.task_id == task_id

    async def test_generic_exception_wraps_in_llm_validation_error(self) -> None:
        """Произвольное исключение оборачивается в LlmValidationError."""

        adapter = MagicMock()
        adapter.provider = "mock"
        adapter.model_name = "test"
        adapter.generate_json = AsyncMock(side_effect=RuntimeError("boom"))
        validator = WordingValidator(adapter)
        session = AsyncMock()
        task_id = uuid4()

        with pytest.raises(LlmValidationError) as exc_info:
            await validator.validate(
                session=session,
                task_id=task_id,
                iteration_id=uuid4(),
                task_type=7,
                subtype="image_size",
                wording="Текст",
                reference_answer=10,
            )
        assert exc_info.value.task_id == task_id
