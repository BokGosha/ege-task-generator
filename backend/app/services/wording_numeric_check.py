"""
Детерминированная численная проверка формулировки.

Не использует LLM. Гарантирует, что все значимые целочисленные параметры
задачи присутствуют в тексте формулировки как отдельные числовые токены.
Это страховка от случая, когда LLM-генератор искажает число (например,
пишет 1042 вместо 1024) или вовсе теряет параметр в пересказе.
"""

import re
from typing import Any

EXCLUDED_KEYS: frozenset[str] = frozenset(
    {"task_type", "kind", "subtype", "difficulty", "topic", "units", "condition"}
)

DERIVED_PARAMS_KEY: str = "_derived_params"

MIN_VALUE_TO_CHECK: int = 10

_NUMBER_TOKEN_RE = re.compile(r"\d+")

_GROUPED_NUMBER_RE = re.compile(r"\b\d{1,3}(?:[ \s]\d{3})+\b")


def _extract_number_tokens(text: str) -> set[str]:
    """Возвращает множество максимальных последовательностей цифр в тексте."""

    tokens: set[str] = set(_NUMBER_TOKEN_RE.findall(text))
    for match in _GROUPED_NUMBER_RE.finditer(text):
        tokens.add(re.sub(r"\s+", "", match.group(0)))
    return tokens


def find_missing_params(
        wording: str,
        params: dict[str, Any],
        target_param: str,
) -> list[tuple[str, int]]:
    """Возвращает список пар (имя_параметра, ожидаемое_значение),
    отсутствующих в тексте формулировки.

    Пустой список означает, что все значимые параметры присутствуют.
    """

    tokens = _extract_number_tokens(wording)
    derived = set(params.get(DERIVED_PARAMS_KEY) or ())
    missing: list[tuple[str, int]] = []

    for key, value in params.items():
        if key.startswith("_"):
            continue
        if key in EXCLUDED_KEYS or key == target_param or key in derived:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if value < MIN_VALUE_TO_CHECK:
            continue
        if str(value) not in tokens:
            missing.append((key, value))

    return missing


def format_feedback(missing: list[tuple[str, int]]) -> str:
    """Формирует текстовое замечание для подмешивания в промпт повтора."""

    if not missing:
        return ""
    parts = ", ".join(f"{key}={value}" for key, value in missing)
    return (
        "Критерий 'numeric_match': в тексте формулировки отсутствуют "
        f"следующие числовые параметры задачи: {parts}. "
        "Все эти значения должны присутствовать в условии дословно."
    )
