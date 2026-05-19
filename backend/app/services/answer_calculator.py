"""
Детерминированное вычисление эталонного ответа по параметрам задания.
Чистая функция без побочных эффектов.
"""

from typing import Any

from backend.app.generators.task11 import _recompute_answer_11
from backend.app.generators.task7 import _recompute_answer_7


def calculate_answer(task_type: int, subtype: str, params: dict[str, Any], target_param: str) -> int:
    """Вычисляет эталонный ответ для задания ЕГЭ."""

    if task_type == 7:
        return _recompute_answer_7(subtype, params, target_param)
    elif task_type == 11:
        return _recompute_answer_11(subtype, params, target_param)
    else:
        raise ValueError(f"Неподдерживаемый тип задания: {task_type}")
