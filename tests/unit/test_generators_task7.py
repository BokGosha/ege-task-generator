"""
Unit-тесты генератора параметров задания 7 ЕГЭ (кодирование изображений и звука).
"""

import math
from typing import Any

import pytest

from backend.app.generators.task7 import (
    MAX_REFERENCE_ANSWER,
    SUBTYPES_7,
    _recompute_answer_7,
    generate_params_7,
    is_valid_params_7,
)
from backend.app.services.answer_calculator import calculate_answer


class TestGenerateParamsTask7:
    """Поведение generate_params_7 при разных входных данных."""

    @pytest.mark.parametrize("subtype", SUBTYPES_7)
    def test_covers_all_subtypes(self, subtype: str) -> None:
        """Генератор возвращает params с корректным subtype и непустым target_param для каждого подтипа."""

        params, target_param, answer = generate_params_7(subtype=subtype)

        assert params["subtype"] == subtype
        assert target_param
        assert isinstance(answer, int)

    @pytest.mark.parametrize("subtype", SUBTYPES_7)
    def test_generated_params_pass_own_validator(self, subtype: str) -> None:
        """Параметры из generate_params_7 проходят is_valid_params_7 на 20 прогонах."""

        for _ in range(20):
            params, target_param, answer = generate_params_7(subtype=subtype)
            valid, reason = is_valid_params_7(params, target_param, answer)
            assert valid, f"Подтип {subtype}: невалидные параметры — {reason}"

    @pytest.mark.parametrize("subtype", SUBTYPES_7)
    def test_generated_answer_matches_calculate_answer(self, subtype: str) -> None:
        """Ответ из generate_params_7 совпадает с независимым пересчётом через calculate_answer."""

        for _ in range(10):
            params, target_param, answer = generate_params_7(subtype=subtype)
            recomputed = calculate_answer(7, subtype, params, target_param)
            assert recomputed == answer, (
                f"Подтип {subtype}: calculate_answer={recomputed}, "
                f"generate_params_7={answer}"
            )

    def test_rejects_unknown_subtype(self) -> None:
        """Передача несуществующего подтипа вызывает ValueError."""

        with pytest.raises(ValueError, match="Неподдерживаемый подтип"):
            generate_params_7(subtype="ghost_subtype")

    def test_without_subtype_picks_valid_one(self) -> None:
        """Вызов без subtype выбирает случайный подтип из SUBTYPES_7."""

        for _ in range(30):
            params, _, _ = generate_params_7()
            assert params["subtype"] in SUBTYPES_7


class TestIsValidParamsTask7:
    """Граничные условия валидатора is_valid_params_7."""

    def _base_params(self) -> dict[str, Any]:
        """Возвращает корректный набор параметров для подтипа image_size."""

        return {
            "task_type": "7",
            "kind": "image",
            "subtype": "image_size",
            "difficulty": "easy",
            "width": 1024,
            "height": 768,
            "bits_per_pixel": 24,
            "image_size_kb": 2304,
            "units": "KB",
        }

    def test_rejects_missing_required_keys(self) -> None:
        """Отсутствие обязательного ключа приводит к отклонению."""

        params = self._base_params()
        del params["task_type"]

        valid, reason = is_valid_params_7(params, "image_size_kb", 2304)

        assert not valid
        assert "Отсутствуют обязательные ключи" in reason

    def test_rejects_nonpositive_answer(self) -> None:
        """answer <= 0 отклоняется валидатором."""

        params = self._base_params()

        for bad_answer in (0, -1, -100):
            valid, reason = is_valid_params_7(params, "image_size_kb", bad_answer)
            assert not valid, f"answer={bad_answer} должен отклоняться"
            assert "положительным целым числом" in reason

    def test_rejects_overflow_answer(self) -> None:
        """answer > MAX_REFERENCE_ANSWER отклоняется."""

        params = self._base_params()
        overflow_answer = MAX_REFERENCE_ANSWER + 1

        valid, reason = is_valid_params_7(params, "image_size_kb", overflow_answer)

        assert not valid
        assert "превышает максимум" in reason

    def test_rejects_unknown_subtype(self) -> None:
        """params["subtype"] вне SUBTYPES_7 возвращает False."""

        params = self._base_params()
        params["subtype"] = "ghost"

        valid, reason = is_valid_params_7(params, "image_size_kb", 2304)

        assert not valid
        assert "Неизвестный подтип" in reason

    def test_rejects_missing_target_param(self) -> None:
        """target_param, отсутствующий в params, приводит к отклонению."""

        params = self._base_params()

        valid, reason = is_valid_params_7(params, "nonexistent_key", 2304)

        assert not valid
        assert "отсутствует в params" in reason

    def test_rejects_nan_or_inf(self) -> None:
        """NaN или Inf в числовом поле отклоняется."""

        params = self._base_params()
        params["width"] = float("nan")

        valid, reason = is_valid_params_7(params, "image_size_kb", 2304)

        assert not valid
        assert "NaN" in reason or "Inf" in reason

        params["width"] = float("inf")
        valid, reason = is_valid_params_7(params, "image_size_kb", 2304)
        assert not valid

    def test_rejects_on_recompute_mismatch(self) -> None:
        """Если answer не совпадает с _recompute_answer_7, набор отклоняется."""

        params = self._base_params()
        wrong_answer = 9999

        valid, reason = is_valid_params_7(params, "image_size_kb", wrong_answer)

        assert not valid
        assert "не совпадает" in reason

    def test_accepts_correct_handmade_params(self) -> None:
        """Вручную собранный корректный набор проходит валидатор."""

        params = self._base_params()
        valid, reason = is_valid_params_7(params, "image_size_kb", 2304)
        assert valid, f"Должен быть валидным, причина отклонения: {reason}"

    def test_recompute_formula_image_size(self) -> None:
        """_recompute_answer_7 для image_size даёт width × height × bpp / 8 / 1024."""

        params = {
            "task_type": "7",
            "subtype": "image_size",
            "units": "KB",
            "width": 1024,
            "height": 768,
            "bits_per_pixel": 24,
            "image_size_kb": 0,
        }
        result = _recompute_answer_7("image_size", params, "image_size_kb")
        expected = int(1024 * 768 * 24 / 8 / 1024)
        assert result == expected


class TestStressBigIntBounds:
    """Стресс-тест на границу BIGINT."""

    @pytest.mark.parametrize("subtype", SUBTYPES_7)
    def test_generated_answer_stays_within_bigint(self, subtype: str) -> None:
        """На 50 прогонах ответ не превышает MAX_REFERENCE_ANSWER."""

        for _ in range(50):
            _, _, answer = generate_params_7(subtype=subtype)
            assert 0 < answer <= MAX_REFERENCE_ANSWER, (
                f"Подтип {subtype}: answer={answer} вне допустимого диапазона"
            )
