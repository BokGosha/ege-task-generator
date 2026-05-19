"""
Unit-тесты построения промпта WordingGenerator._build_prompt.
"""

import pytest
from unittest.mock import MagicMock

from backend.app.services.wording_generator import WordingGenerator
from backend.app.services.prompt_loader import load_prompt


def _few_shot_7(subtype: str) -> str:
    return load_prompt(f"task7/few_shot/{subtype}.txt")


def _few_shot_11(subtype: str) -> str:
    return load_prompt(f"task11/few_shot/{subtype}.txt")


class TestBuildPromptBasic:
    """Проверяет основу промпта — обязательные компоненты."""

    def _make_generator(self):
        adapter = MagicMock()
        return WordingGenerator(adapter)

    def test_contains_task_type_and_subtype(self) -> None:
        """Промпт содержит тип и подтип задания."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=7,
            subtype="image_size",
            params={"width": 1024, "height": 768, "color_depth": 24},
            target_param="image_size",
            reference_answer=2359296,
        )
        assert "7" in prompt
        assert "image_size" in prompt

    def test_contains_reference_answer(self) -> None:
        """Промпт содержит правильный ответ."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=7,
            subtype="sound_duration",
            params={"freq": 44100, "depth": 16, "channels": 2, "file_size_bytes": 10000},
            target_param="sound_duration",
            reference_answer=42,
        )
        assert "42" in prompt

    def test_params_included_except_excluded_keys(self) -> None:
        """Параметры задания включены в промпт, кроме служебных ключей."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=11,
            subtype="min_alphabet_size",
            params={
                "task_type": 11,
                "subtype": "min_alphabet_size",
                "difficulty": "medium",
                "topic": "кодирование",
                "units": "бит",
                "serial_length": 10,
                "extra_bytes": 5,
                "num_objects": 100,
                "min_alphabet_size": 16,
            },
            target_param="min_alphabet_size",
            reference_answer=16,
        )
        assert "serial_length" in prompt
        assert "extra_bytes" in prompt
        assert "num_objects" in prompt


class TestBuildPromptFewShot:
    """Проверяет подстановку few-shot примеров."""

    def _make_generator(self):
        adapter = MagicMock()
        return WordingGenerator(adapter)

    def test_few_shot_for_task7_is_subtype_specific(self) -> None:
        """Для типа 7 подставляются примеры конкретного подтипа."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=7,
            subtype="image_size",
            params={"width": 100, "height": 100},
            target_param="image_size",
            reference_answer=100,
        )
        assert "Пример 1" in prompt
        assert _few_shot_7("image_size")[:80] in prompt
        assert _few_shot_7("sound_bit_depth")[:80] not in prompt

    def test_formalism_block_present_for_task7(self) -> None:
        """Для задания 7 промпт содержит обязательные ЕГЭ-формализмы."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=7,
            subtype="image_size",
            params={"width": 100, "height": 100},
            target_param="image_size",
            reference_answer=100,
        )
        assert "Единица измерения ответа" in prompt
        assert "бит на пиксель" in prompt

    def test_few_shot_for_task11_is_subtype_specific(self) -> None:
        """Для типа 11 подставляются примеры конкретного подтипа."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=11,
            subtype="max_serial_length",
            params={"alphabet_size": 26, "extra_bytes": 4},
            target_param="max_serial_length",
            reference_answer=7,
        )
        assert "Пример 1" in prompt
        assert _few_shot_11("max_serial_length")[:80] in prompt

    def test_formalism_block_present_for_task11(self) -> None:
        """Для задания 11 промпт содержит обязательные ЕГЭ-формализмы."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=11,
            subtype="min_alphabet_size",
            params={"alphabet_size": 26, "serial_length": 10},
            target_param="min_alphabet_size",
            reference_answer=16,
        )
        assert "посимвольное кодирование" in prompt
        assert "минимально возможное целое число байт" in prompt

    def test_task11_formalism_absent_for_task7(self) -> None:
        """Для задания 7 блок формализации задания 11 не подставляется."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=7,
            subtype="image_size",
            params={"width": 100, "height": 100},
            target_param="image_size",
            reference_answer=100,
        )
        assert "посимвольное кодирование" not in prompt

    def test_no_few_shot_for_unknown_type(self) -> None:
        """Для неизвестного типа few-shot пустые, но промпт формируется без ошибки."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=999,
            subtype="any",
            params={"a": 1},
            target_param="a",
            reference_answer=1,
        )
        assert "999" in prompt


class TestBuildPromptFeedback:
    """Проверяет добавление секции обратной связи."""

    def _make_generator(self):
        adapter = MagicMock()
        return WordingGenerator(adapter)

    def test_no_feedback_no_section(self) -> None:
        """Без feedback секция замечаний отсутствует в промпте."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=7,
            subtype="image_size",
            params={"w": 10},
            target_param="image_size",
            reference_answer=50,            previous_feedbacks=None,
            previous_wording=None,
        )
        assert "отклонена валидатором" not in prompt
        assert "отклонены валидатором" not in prompt

    def test_with_feedback_adds_correction_section(self) -> None:
        """С feedback промпт содержит секцию замечаний и текст обратной связи."""

        gen = self._make_generator()
        feedback = "Критерий 'clarity': Формулировка неясна."
        prompt = gen._build_prompt(
            task_type=7,
            subtype="image_size",
            params={"w": 10},
            target_param="image_size",
            reference_answer=50,
            previous_feedbacks=[feedback],
            previous_wording=None,
        )
        assert "отклонены валидатором" in prompt
        assert feedback in prompt
        assert "исправь" in prompt.lower()

    def test_accumulated_feedbacks_all_in_prompt(self) -> None:
        """Все накопленные замечания попадают в промпт с номерами итераций."""

        gen = self._make_generator()
        feedbacks = [
            "Критерий 'clarity': неясно",
            "Критерий 'consistency': противоречие",
        ]
        prompt = gen._build_prompt(
            task_type=7,
            subtype="image_size",
            params={"w": 10},
            target_param="image_size",
            reference_answer=50,
            previous_feedbacks=feedbacks,
            previous_wording=None,
        )
        for fb in feedbacks:
            assert fb in prompt
        assert "Итерация 1" in prompt
        assert "Итерация 2" in prompt

    def test_previous_wording_included_when_provided(self) -> None:
        """previous_wording подмешивается в промпт как ориентир для правки."""

        gen = self._make_generator()
        prev = "Старая формулировка задания с ошибкой."
        prompt = gen._build_prompt(
            task_type=7,
            subtype="image_size",
            params={"w": 10},
            target_param="image_size",
            reference_answer=50,
            previous_feedbacks=["fb"],
            previous_wording=prev,
        )
        assert prev in prompt

    def test_previous_wording_ignored_without_feedbacks(self) -> None:
        """Без feedbacks секция правки не добавляется, даже если есть wording."""

        gen = self._make_generator()
        prompt = gen._build_prompt(
            task_type=7,
            subtype="image_size",
            params={"w": 10},
            target_param="image_size",
            reference_answer=50,
            previous_feedbacks=None,
            previous_wording="что-то",
        )
        assert "что-то" not in prompt
