"""
Генератор параметров для задания 11 ЕГЭ по информатике
(серийные номера, посимвольное кодирование).
"""

import math
import random
from typing import Any, Callable

MAX_REFERENCE_ANSWER: int = 2 ** 31 - 1

_SubtypeGenerator = Callable[[], tuple[dict[str, Any], str, int]]
_GENERATORS: dict[str, _SubtypeGenerator] = {}


def _register(name: str) -> Callable[[_SubtypeGenerator], _SubtypeGenerator]:
    """Регистрирует функцию-генератор параметров под именем подтипа."""

    def wrap(fn: _SubtypeGenerator) -> _SubtypeGenerator:
        _GENERATORS[name] = fn
        return fn

    return wrap


@_register("min_alphabet_size")
def _gen_min_alphabet_size() -> tuple[dict[str, Any], str, int]:
    serial_length = random.choice([105, 248, 2783])
    nums = random.choice([100, 300, 800])
    memory_kb = random.choice([7, 11, 15])

    memory_bytes = memory_kb * 1024
    bytes_per_serial = math.ceil(memory_bytes / nums)
    bits_per_symbol = math.ceil(bytes_per_serial * 8 / serial_length)
    min_alphabet_size = 2 ** bits_per_symbol

    params = {
        "task_type": "11",
        "subtype": "min_alphabet_size",
        "difficulty": "hard",
        "serial_length": serial_length,
        "nums": nums,
        "memory_kb": memory_kb,
        "min_alphabet_size": min_alphabet_size,
        "units": "symbols",
        "condition": "не менее",
    }
    return params, "min_alphabet_size", min_alphabet_size


@_register("max_serial_length")
def _gen_max_serial_length() -> tuple[dict[str, Any], str, int]:
    digits = 10
    latin_letters = 52
    special_chars = random.choice([1989, 963, 450, 70])
    alphabet_size = digits + latin_letters + special_chars

    nums = random.choice([836, 2000, 5000])
    memory_kb = random.choice([639, 100, 200])

    bytes_per_serial = math.floor(memory_kb * 1024 / nums)
    bits_per_symbol = math.ceil(math.log2(alphabet_size))
    max_serial_length = math.floor(bytes_per_serial * 8 / bits_per_symbol)

    params = {
        "task_type": "11",
        "subtype": "max_serial_length",
        "difficulty": "medium",
        "digits": digits,
        "latin_letters": latin_letters,
        "special_chars": special_chars,
        "alphabet_size": alphabet_size,
        "nums": nums,
        "memory_kb": memory_kb,
        "max_serial_length": max_serial_length,
        "units": "symbols",
        "condition": "не более",
        "_derived_params": ["alphabet_size", "digits", "latin_letters"],
    }
    return params, "max_serial_length", max_serial_length


@_register("min_serial_length")
def _gen_min_serial_length() -> tuple[dict[str, Any], str, int]:
    digits = 10
    special_chars = random.choice([17, 70, 100])
    alphabet_size = digits + special_chars

    nums = random.choice([7564230, 10000000])
    memory_mb = random.choice([31, 50])

    memory_bytes = memory_mb * 1024 * 1024
    bytes_per_serial = math.ceil(memory_bytes / nums)
    bits_per_symbol = math.ceil(math.log2(alphabet_size))
    min_serial_length = math.ceil(bytes_per_serial * 8 / bits_per_symbol)

    params = {
        "task_type": "11",
        "subtype": "min_serial_length",
        "difficulty": "medium",
        "digits": digits,
        "special_chars": special_chars,
        "alphabet_size": alphabet_size,
        "nums": nums,
        "memory_mb": memory_mb,
        "min_serial_length": min_serial_length,
        "units": "symbols",
        "condition": "более",
        "_derived_params": ["alphabet_size", "digits"],
    }
    return params, "min_serial_length", min_serial_length


@_register("max_extra_bytes")
def _gen_max_extra_bytes() -> tuple[dict[str, Any], str, int]:
    serial_length = random.choice([18, 25])
    digits = 10
    latin_upper = 26
    latin_lower = 26
    special_chars = 70
    alphabet_size = digits + latin_upper + latin_lower + special_chars

    nums = random.choice([2000, 3000])
    memory_kb = random.choice([100, 150])

    bits_per_symbol = math.ceil(math.log2(alphabet_size))
    bytes_per_serial = math.ceil(serial_length * bits_per_symbol / 8)
    total_extra_bytes = memory_kb * 1024 - nums * bytes_per_serial
    max_extra_bytes = math.floor(total_extra_bytes / nums)

    params = {
        "task_type": "11",
        "subtype": "max_extra_bytes",
        "difficulty": "hard",
        "serial_length": serial_length,
        "digits": digits,
        "latin_upper": latin_upper,
        "latin_lower": latin_lower,
        "special_chars": special_chars,
        "alphabet_size": alphabet_size,
        "nums": nums,
        "memory_kb": memory_kb,
        "max_extra_bytes": max_extra_bytes,
        "units": "bytes",
        "condition": "не более",
        "_derived_params": ["alphabet_size", "digits", "latin_upper", "latin_lower"],
    }
    return params, "max_extra_bytes", max_extra_bytes


SUBTYPES_11: list[str] = list(_GENERATORS.keys())


def generate_params_11(subtype: str | None = None) -> tuple[dict[str, Any], str, int]:
    """Генерирует параметры для задачи 11."""

    if subtype is None:
        subtype = random.choice(SUBTYPES_11)
    elif subtype not in _GENERATORS:
        raise ValueError(f"Неподдерживаемый подтип для задания 11: {subtype}")

    params, target_param, answer = _GENERATORS[subtype]()
    params.setdefault("topic", params.get("subtype"))
    return params, target_param, answer


def is_valid_params_11(params: dict[str, Any], target_param: str, answer: int) -> tuple[bool, str]:
    """Проверяет допустимость параметров задания 11."""

    required_common = {"task_type", "subtype", "units"}
    if not required_common.issubset(params.keys()):
        missing = required_common - params.keys()
        return False, f"Отсутствуют обязательные ключи: {missing}"

    subtype = params.get("subtype")
    if subtype not in SUBTYPES_11:
        return False, f"Неизвестный подтип: {subtype}"

    if target_param not in params:
        return False, f"target_param '{target_param}' отсутствует в params"

    if not isinstance(answer, int) or answer <= 0:
        return False, f"Ответ должен быть положительным целым числом, получено: {answer}"

    if answer > MAX_REFERENCE_ANSWER:
        return False, (
            f"Ответ {answer} превышает максимум {MAX_REFERENCE_ANSWER} "
            f"для подтипа '{subtype}' — параметры сгенерированы некорректно"
        )

    numeric_keys = _get_numeric_keys_11(subtype)
    for key in numeric_keys:
        val = params.get(key)
        if val is None:
            return False, f"Числовой параметр '{key}' отсутствует для подтипа '{subtype}'"
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return False, f"Параметр '{key}' содержит NaN или Inf"

    try:
        recomputed = _recompute_answer_11(subtype, params, target_param)
        if recomputed != answer:
            return False, (
                f"Пересчитанный ответ ({recomputed}) не совпадает "
                f"с заявленным ({answer}) для подтипа '{subtype}'"
            )
    except Exception as e:
        return False, f"Ошибка при пересчёте ответа: {e}"

    return True, ""


def _get_numeric_keys_11(subtype: str) -> list[str]:
    """Возвращает список числовых ключей для подтипа задания 11."""

    mapping: dict[str, list[str]] = {
        "min_alphabet_size": ["serial_length", "nums", "memory_kb"],
        "max_serial_length": [
            "digits", "latin_letters", "special_chars", "alphabet_size",
            "nums", "memory_kb",
        ],
        "min_serial_length": [
            "digits", "special_chars", "alphabet_size",
            "nums", "memory_mb",
        ],
        "max_extra_bytes": [
            "serial_length", "digits", "latin_upper", "latin_lower",
            "special_chars", "alphabet_size", "nums", "memory_kb",
        ],
    }
    return mapping.get(subtype, [])


def _recompute_answer_11(subtype: str, params: dict, target_param: str) -> int:
    """Пересчитывает ответ для задания 11 на основе параметров."""

    if subtype == "min_alphabet_size":
        memory_bytes = params["memory_kb"] * 1024
        bytes_per_serial = math.ceil(memory_bytes / params["nums"])
        bits_per_symbol = math.ceil(bytes_per_serial * 8 / params["serial_length"])
        return 2 ** bits_per_symbol

    elif subtype == "max_serial_length":
        bytes_per_serial = math.floor(params["memory_kb"] * 1024 / params["nums"])
        bits_per_symbol = math.ceil(math.log2(params["alphabet_size"]))
        return math.floor(bytes_per_serial * 8 / bits_per_symbol)

    elif subtype == "min_serial_length":
        memory_bytes = params["memory_mb"] * 1024 * 1024
        bytes_per_serial = math.ceil(memory_bytes / params["nums"])
        bits_per_symbol = math.ceil(math.log2(params["alphabet_size"]))
        return math.ceil(bytes_per_serial * 8 / bits_per_symbol)

    elif subtype == "max_extra_bytes":
        bits_per_symbol = math.ceil(math.log2(params["alphabet_size"]))
        bytes_per_serial = math.ceil(params["serial_length"] * bits_per_symbol / 8)
        total_extra = params["memory_kb"] * 1024 - params["nums"] * bytes_per_serial
        return math.floor(total_extra / params["nums"])

    raise ValueError(f"Неизвестный подтип для пересчёта: {subtype}")
