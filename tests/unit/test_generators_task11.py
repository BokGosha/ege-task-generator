"""
Unit-тесты генератора параметров задания 11 ЕГЭ (серийные номера, посимвольное кодирование).
"""

import math
from typing import Any

import pytest

from backend.app.generators.task11 import (
    MAX_REFERENCE_ANSWER,
    SUBTYPES_11,
    _recompute_answer_11,
    generate_params_11,
    is_valid_params_11,
)
from backend.app.services.answer_calculator import calculate_answer


class TestGenerateParamsTask11:
    """Поведение generate_params_11 при разных входных данных."""

    @pytest.mark.parametrize("subtype", SUBTYPES_11)
    def test_covers_all_subtypes(self, subtype: str) -> None:
        """Генератор возвращает params с корректным subtype для каждого подтипа."""

        params, target_param, answer = generate_params_11(subtype=subtype)

        assert params["subtype"] == subtype
        assert target_param == subtype
        assert isinstance(answer, int)

    @pytest.mark.parametrize("subtype", SUBTYPES_11)
    def test_generated_params_pass_own_validator(self, subtype: str) -> None:
        """Параметры из generate_params_11 проходят is_valid_params_11 на 20 прогонах."""

        for _ in range(20):
            params, target_param, answer = generate_params_11(subtype=subtype)
            valid, reason = is_valid_params_11(params, target_param, answer)
            assert valid, f"Подтип {subtype}: невалидные параметры — {reason}"

    @pytest.mark.parametrize("subtype", SUBTYPES_11)
    def test_generated_answer_matches_calculate_answer(self, subtype: str) -> None:
        """Ответ из generate_params_11 совпадает с независимым пересчётом через calculate_answer."""

        for _ in range(10):
            params, target_param, answer = generate_params_11(subtype=subtype)
            recomputed = calculate_answer(11, subtype, params, target_param)
            assert recomputed == answer, (
                f"Подтип {subtype}: calculate_answer={recomputed}, "
                f"generate_params_11={answer}"
            )

    def test_rejects_unknown_subtype(self) -> None:
        """Передача несуществующего подтипа вызывает ValueError."""

        with pytest.raises(ValueError, match="Неподдерживаемый подтип"):
            generate_params_11(subtype="ghost_subtype")

    def test_without_subtype_picks_valid_one(self) -> None:
        """Вызов без subtype выбирает случайный подтип из SUBTYPES_11."""

        for _ in range(30):
            params, _, _ = generate_params_11()
            assert params["subtype"] in SUBTYPES_11


class TestIsValidParamsTask11:
    """Граничные условия валидатора is_valid_params_11."""

    def _base_params(self) -> dict[str, Any]:
        """Возвращает корректный набор параметров для подтипа min_alphabet_size."""

        return {
            "task_type": "11",
            "subtype": "min_alphabet_size",
            "difficulty": "hard",
            "serial_length": 105,
            "nums": 300,
            "memory_kb": 15,
            "min_alphabet_size": _recompute_answer_11(
                "min_alphabet_size",
                {"serial_length": 105, "nums": 300, "memory_kb": 15},
                "min_alphabet_size",
            ),
            "units": "symbols",
            "condition": "не менее",
        }

    def test_rejects_missing_required_keys(self) -> None:
        """Отсутствие обязательного ключа возвращает ошибку."""

        params = self._base_params()
        del params["units"]

        valid, reason = is_valid_params_11(
            params, "min_alphabet_size", params.get("min_alphabet_size", 1),
        )

        assert not valid
        assert "Отсутствуют обязательные ключи" in reason

    def test_rejects_nonpositive_answer(self) -> None:
        """answer <= 0 отклоняется для любого подтипа."""

        params = self._base_params()

        for bad_answer in (0, -1, -42):
            valid, reason = is_valid_params_11(params, "min_alphabet_size", bad_answer)
            assert not valid, f"answer={bad_answer} должен отклоняться"
            assert "положительным целым числом" in reason

    def test_rejects_overflow_answer(self) -> None:
        """answer > MAX_REFERENCE_ANSWER отклоняется."""

        params = self._base_params()
        overflow = MAX_REFERENCE_ANSWER + 1

        valid, reason = is_valid_params_11(params, "min_alphabet_size", overflow)

        assert not valid
        assert "превышает максимум" in reason

    def test_rejects_unknown_subtype(self) -> None:
        """subtype вне SUBTYPES_11 возвращает ошибку."""

        params = self._base_params()
        params["subtype"] = "ghost"

        valid, reason = is_valid_params_11(
            params, "min_alphabet_size", params["min_alphabet_size"],
        )

        assert not valid
        assert "Неизвестный подтип" in reason

    def test_rejects_missing_target_param(self) -> None:
        """target_param, отсутствующий в params, приводит к отклонению."""

        params = self._base_params()

        valid, reason = is_valid_params_11(params, "nonexistent_key", 42)

        assert not valid
        assert "отсутствует в params" in reason

    def test_rejects_nan_numeric_field(self) -> None:
        """NaN в числовом поле отклоняется."""

        params = self._base_params()
        params["serial_length"] = float("nan")

        valid, reason = is_valid_params_11(
            params, "min_alphabet_size", params["min_alphabet_size"],
        )

        assert not valid
        assert "NaN" in reason or "Inf" in reason

    def test_rejects_on_recompute_mismatch(self) -> None:
        """Если answer не совпадает с _recompute_answer_11, набор отклоняется."""

        params = self._base_params()
        wrong_answer = params["min_alphabet_size"] + 1
        params["min_alphabet_size"] = wrong_answer

        valid, reason = is_valid_params_11(params, "min_alphabet_size", wrong_answer)

        assert not valid
        assert "не совпадает" in reason


class TestStressBigIntBounds:
    """Стресс-тест границы BIGINT для задания 11."""

    @pytest.mark.parametrize("subtype", SUBTYPES_11)
    def test_generated_answer_stays_within_bigint(self, subtype: str) -> None:
        """На 50 прогонах ответ не превышает MAX_REFERENCE_ANSWER."""

        for _ in range(50):
            _, _, answer = generate_params_11(subtype=subtype)
            assert 0 < answer <= MAX_REFERENCE_ANSWER, (
                f"Подтип {subtype}: answer={answer} вне допустимого диапазона"
            )
