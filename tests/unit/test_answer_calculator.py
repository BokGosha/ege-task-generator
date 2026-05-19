"""
Тест детерминированной воспроизводимости answer_calculator.
Одинаковые входные параметры всегда дают одинаковый эталонный ответ.
"""

import pytest

from backend.app.services.answer_calculator import calculate_answer


class TestAnswerCalculatorReproducibility:
    """Одинаковые входные параметры дают одинаковый ответ при многократном запуске."""

    @pytest.mark.parametrize("task_type,subtype,params,target_param,expected", [
        (
                7,
                "image_size",
                {"width": 1024, "height": 768, "bits_per_pixel": 24, "image_size_kb": 2304},
                "image_size_kb",
                2304,
        ),
        (
                7,
                "colors_count",
                {
                    "width": 512, "height": 384, "image_size_kb": 200,
                    "bits_per_pixel": 9, "palette_colors": 512,
                },
                "palette_colors",
                512,
        ),
        (
                7,
                "sound_self_duration",
                {
                    "channels": 2, "bit_depth": 16, "sample_rate_hz": 44100,
                    "file_size_kb": 1024, "duration_sec": 2,
                },
                "duration_sec",
                5,
        ),
        (
                11,
                "min_alphabet_size",
                {
                    "serial_length": 105, "nums": 65536,
                    "memory_mb": 7, "min_alphabet_size": 16,
                },
                "min_alphabet_size",
                16,
        ),
        (
                11,
                "max_serial_length",
                {
                    "digits": 10, "latin_letters": 52, "special_chars": 1989,
                    "alphabet_size": 2051, "nums": 836, "memory_kb": 639,
                    "max_serial_length": 56,
                },
                "max_serial_length",
                56,
        ),
    ])
    def test_reproducibility(self, task_type, subtype, params, target_param, expected):
        """Повторные вызовы с одними параметрами дают один результат."""

        results = [
            calculate_answer(task_type, subtype, params, target_param)
            for _ in range(10)
        ]
        assert all(r == results[0] for r in results)
        assert isinstance(results[0], int)

    def test_unsupported_type_raises(self):
        """Неподдерживаемый тип вызывает ValueError."""

        with pytest.raises(ValueError, match="Неподдерживаемый тип"):
            calculate_answer(99, "any", {}, "any")

    @pytest.mark.parametrize("task_type,subtype,params,target_param,expected", [
        (
                7,
                "image_size",
                {"width": 640, "height": 480, "bits_per_pixel": 8, "image_size_kb": 300},
                "image_size_kb",
                300,
        ),
        (
                11,
                "max_extra_bytes",
                {
                    "serial_length": 18, "digits": 10, "latin_upper": 26,
                    "latin_lower": 26, "special_chars": 70, "alphabet_size": 132,
                    "nums": 2000, "memory_kb": 100,
                },
                "max_extra_bytes",
                None,
        ),
    ])
    def test_deterministic_value(self, task_type, subtype, params, target_param, expected):
        """Конкретные значения совпадают с ожиданиями."""

        result = calculate_answer(task_type, subtype, params, target_param)
        assert isinstance(result, int)
        if expected is not None:
            assert result == expected
