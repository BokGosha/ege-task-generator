"""Unit-тесты детерминированной численной проверки формулировки."""

import pytest

from backend.app.services.wording_numeric_check import (
    find_missing_params,
    format_feedback,
)


class TestFindMissingParams:
    """Базовое поведение поиска отсутствующих параметров в тексте."""

    def test_all_params_present_returns_empty(self) -> None:
        """Если все числа присутствуют, missing — пустой."""

        wording = "Изображение 1024 на 768 пикселей с глубиной 24 бита на пиксель."
        params = {"width": 1024, "height": 768, "bits_per_pixel": 24}
        assert find_missing_params(wording, params, target_param="image_size_kb") == []

    def test_missing_param_detected(self) -> None:
        """Если хотя бы один параметр пропущен — он в результате."""

        wording = "Изображение 1024 на 768 пикселей." # bits_per_pixel пропущен
        params = {"width": 1024, "height": 768, "bits_per_pixel": 24}
        missing = find_missing_params(wording, params, target_param="image_size_kb")
        assert missing == [("bits_per_pixel", 24)]

    def test_distorted_number_treated_as_missing(self) -> None:
        """Опечатка в числе LLM (1042 вместо 1024) ловится как пропуск."""

        wording = "Изображение 1042 на 768 пикселей с глубиной 24 бита."
        params = {"width": 1024, "height": 768, "bits_per_pixel": 24}
        missing = find_missing_params(wording, params, target_param="image_size_kb")
        assert ("width", 1024) in missing

    def test_substring_collision_not_match(self) -> None:
        """Число 1024 не должно засчитываться, если в тексте есть только 10240."""

        wording = "Размер файла составил 10240 байт."
        params = {"width": 1024}
        missing = find_missing_params(wording, params, target_param="answer")
        assert ("width", 1024) in missing


class TestExclusions:
    """Пропуск параметров, которые не должны проверяться."""

    def test_target_param_skipped(self) -> None:
        """target_param никогда не должен попасть в missing — это эталонный ответ."""

        wording = "Картинка 1024 на 768."
        params = {"width": 1024, "height": 768, "image_size_kb": 2359296}
        missing = find_missing_params(wording, params, target_param="image_size_kb")
        assert ("image_size_kb", 2359296) not in missing

    def test_excluded_keys_skipped(self) -> None:
        """Служебные ключи (task_type, subtype и т.д.) не проверяются."""

        wording = "Текст без чисел вообще."
        params = {
            "task_type": "7",
            "subtype": "image_size",
            "difficulty": "easy",
            "kind": "image",
            "topic": "кодирование",
            "units": "KB",
        }
        assert find_missing_params(wording, params, target_param="x") == []

    def test_small_values_skipped(self) -> None:
        """Значения < 10 пропускаются (слишком шумно: каналы=2, биты=8 и т.п.)."""

        wording = "Стерео 2 канала, без сжатия."
        params = {"channels": 2, "compression": 0}
        assert find_missing_params(wording, params, target_param="x") == []

    def test_non_int_values_skipped(self) -> None:
        """Float и bool значения не проверяются."""

        wording = "Сжатие 35% и без BOM."
        params = {"compression_ratio": 0.35, "has_bom": False}
        assert find_missing_params(wording, params, target_param="x") == []


class TestGroupedDigits:
    """Разрядные пробелы внутри числа («1 000 000») должны распознаваться."""

    def test_million_with_thin_spaces(self) -> None:
        """«1 000 000» в тексте трактуется как 1000000."""

        wording = "Всего необходимо хранить 1 000 000 идентификаторов."
        params = {"nums": 1_000_000}
        assert find_missing_params(wording, params, target_param="x") == []

    def test_thousand_with_space(self) -> None:
        """«10 000» в тексте трактуется как 10000."""

        wording = "В базе 10 000 записей."
        params = {"records": 10_000}
        assert find_missing_params(wording, params, target_param="x") == []

    def test_adjacent_unrelated_numbers_not_merged(self) -> None:
        """«18 180» — два разных числа, не должны склеиваться в 18180.

        Левая группа из 1-3 цифр + правая из >3 — не разрядный разделитель,
        поэтому шаблон не сработает и каждое число останется самостоятельным.
        """

        wording = "Картинка 18 1801 пикселей."
        params = {"size": 181801}
        # 181801 не должно образоваться из склеивания «18 1801»
        missing = find_missing_params(wording, params, target_param="x")
        assert ("size", 181801) in missing

    def test_both_grouped_and_atomic_numbers_present(self) -> None:
        """Одновременно работают и обычные числа, и разрядные."""

        wording = "Алфавит 248 символов, хранится 1 000 000 записей."
        params = {"length": 248, "nums": 1_000_000}
        assert find_missing_params(wording, params, target_param="x") == []


class TestDerivedParams:
    """Производные параметры (alphabet_size = digits+...) не должны проверяться."""

    def test_derived_param_skipped(self) -> None:
        """Параметр, указанный в _derived_params, не требуется в тексте."""

        wording = "10 цифр и 70 спецсимволов."
        params = {
            "digits": 10,
            "special_chars": 70,
            "alphabet_size": 80,
            "_derived_params": ["alphabet_size"],
        }
        assert find_missing_params(wording, params, target_param="x") == []

    def test_non_derived_still_required(self) -> None:
        """Параметры, НЕ помеченные как derived, по-прежнему проверяются."""

        wording = "10 цифр." # special_chars=70 пропущен
        params = {
            "digits": 10,
            "special_chars": 70,
            "alphabet_size": 80,
            "_derived_params": ["alphabet_size"],
        }
        missing = find_missing_params(wording, params, target_param="x")
        assert ("special_chars", 70) in missing
        assert all(key != "alphabet_size" for key, _ in missing)

    def test_underscore_keys_skipped_even_without_derived_list(self) -> None:
        """Любой ключ, начинающийся с '_', игнорируется как служебный."""

        wording = "Текст без чисел."
        params = {"_internal_count": 999}
        assert find_missing_params(wording, params, target_param="x") == []


class TestFormatFeedback:
    """Текстовое замечание для подмешивания в промпт повтора."""

    def test_empty_for_no_missing(self) -> None:
        assert format_feedback([]) == ""

    def test_lists_all_missing_params(self) -> None:
        msg = format_feedback([("width", 1024), ("height", 768)])
        assert "width=1024" in msg
        assert "height=768" in msg
        assert "numeric_match" in msg
