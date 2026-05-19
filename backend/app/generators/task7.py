"""
Генератор параметров для задания 7 ЕГЭ по информатике
(кодирование изображений и звука).
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


@_register("image_size")
def _gen_image_size() -> tuple[dict[str, Any], str, int]:
    width = random.choice([512, 640, 800, 1024])
    height = random.choice([384, 480, 600, 768])
    bits_per_pixel = random.choice([8, 16, 24, 32])

    bits_total = width * height * bits_per_pixel
    image_size_kb = bits_total / 8 / 1024

    answer = int(image_size_kb)
    params = {
        "task_type": "7",
        "kind": "image",
        "subtype": "image_size",
        "difficulty": "easy",
        "width": width,
        "height": height,
        "bits_per_pixel": bits_per_pixel,
        "units": "KB",
    }
    return params, "image_size_kb", answer


@_register("colors_count")
def _gen_colors_count() -> tuple[dict[str, Any], str, int]:
    width = random.choice([512, 768, 1024])
    height = random.choice([384, 576, 768])
    image_size_kb = random.choice([100, 200, 500])

    bits_total = image_size_kb * 1024 * 8
    bits_per_pixel = math.floor(bits_total / (width * height))
    palette_colors = 2 ** bits_per_pixel

    params = {
        "task_type": "7",
        "kind": "image",
        "subtype": "colors_count",
        "difficulty": "medium",
        "width": width,
        "height": height,
        "image_size_kb": image_size_kb,
        "units": "colors",
    }
    return params, "palette_colors", palette_colors


@_register("sound_self_duration")
def _gen_sound_self_duration() -> tuple[dict[str, Any], str, int]:
    channels = random.choice([1, 2, 4])
    bit_depth = random.choice([8, 16, 24])
    sample_rate_hz = random.choice([22050, 44100, 48000])
    file_size_kb = random.choice([2048, 4096, 8192])

    bits_total = file_size_kb * 1024 * 8
    duration_sec = int(bits_total / (channels * sample_rate_hz * bit_depth))

    params = {
        "task_type": "7",
        "kind": "sound",
        "subtype": "sound_self_duration",
        "difficulty": "easy",
        "channels": channels,
        "bit_depth": bit_depth,
        "sample_rate_hz": sample_rate_hz,
        "file_size_kb": file_size_kb,
        "units": "sec",
    }
    return params, "duration_sec", duration_sec


@_register("packet_size")
def _gen_packet_size() -> tuple[dict[str, Any], str, int]:
    width = random.choice([640, 800, 1024, 1280, 1920])
    height = random.choice([480, 600, 720, 960, 1080])
    bits_per_pixel = random.choice([16, 24])

    bytes_per_image = width * height * bits_per_pixel / 8

    target_param = random.choice(["packet_mb", "images_per_packet"])
    if target_param == "packet_mb":
        images_per_packet = random.choice([100, 200, 400, 500])
        packet_mb = math.ceil(bytes_per_image * images_per_packet / (1024 * 1024))
        answer = packet_mb
        condition = "не менее"
    else:
        packet_mb = random.choice([10, 20, 50, 100])
        images_per_packet = int(packet_mb * 1024 * 1024 // bytes_per_image)
        answer = images_per_packet
        condition = "не более"

    params = {
        "task_type": "7",
        "kind": "image",
        "subtype": "packet_size",
        "difficulty": "medium",
        "width": width,
        "height": height,
        "bits_per_pixel": bits_per_pixel,
        "images_per_packet": images_per_packet,
        "packet_mb": packet_mb,
        "units": "MB",
        "condition": condition,
    }
    return params, target_param, answer


@_register("cards_count")
def _gen_cards_count() -> tuple[dict[str, Any], str, int]:
    width = random.choice([1920, 2560, 3840])
    height = random.choice([1080, 1440, 2160])
    bits_per_pixel = random.choice([16, 24, 30])
    compression_ratio = random.choice([0.3, 0.35, 0.4])
    service_overhead_kb = random.choice([64, 80, 120, 256])
    card_capacity_gb = random.choice([8, 16, 20, 32])

    bytes_per_image = width * height * bits_per_pixel / 8
    compressed_kb = bytes_per_image * compression_ratio / 1024
    total_bytes_per_image = (compressed_kb + service_overhead_kb) * 1024
    card_bytes = card_capacity_gb * 1024 * 1024 * 1024

    target_param = random.choice(["cards_needed", "images_count"])
    if target_param == "cards_needed":
        images_count = random.choice([1000, 2000, 4320, 5000])
        cards_needed = math.ceil(total_bytes_per_image * images_count / card_bytes)
        answer = cards_needed
        condition = "не менее"
    else:
        cards_needed = random.choice([2, 3, 4, 5])
        images_count = int(cards_needed * card_bytes // total_bytes_per_image)
        answer = images_count
        condition = "не более"

    params = {
        "task_type": "7",
        "kind": "image",
        "subtype": "cards_count",
        "difficulty": "hard",
        "width": width,
        "height": height,
        "bits_per_pixel": bits_per_pixel,
        "compression_ratio": compression_ratio,
        "service_overhead_kb": service_overhead_kb,
        "images_count": images_count,
        "card_capacity_gb": card_capacity_gb,
        "cards_needed": cards_needed,
        "units": "cards",
        "condition": condition,
    }
    return params, target_param, answer


@_register("traffic_saving")
def _gen_traffic_saving() -> tuple[dict[str, Any], str, int]:
    orig_width = random.choice([1920, 2560])
    orig_height = random.choice([1080, 1440])
    orig_bits_per_pixel = random.choice([24, 30])
    new_width = random.choice([800, 1280, 1600])
    new_height = random.choice([600, 720])
    new_bits_per_pixel = random.choice([16, 24])
    images_count = random.choice([50, 100, 200, 500])

    orig_kb = orig_width * orig_height * orig_bits_per_pixel / 8 / 1024
    new_kb = new_width * new_height * new_bits_per_pixel / 8 / 1024
    saved_kb_per_image = orig_kb - new_kb

    target_param = random.choice(["total_saved_kb", "images_count"])
    if target_param == "total_saved_kb":
        total_saved_kb = int(saved_kb_per_image * images_count)
        answer = total_saved_kb
        condition = "не менее"
    else:
        total_saved_kb = random.choice([20000, 50000, 100000])
        images_count = math.ceil(total_saved_kb / saved_kb_per_image)
        answer = images_count
        condition = "не менее"

    params = {
        "task_type": "7",
        "kind": "image",
        "subtype": "traffic_saving",
        "difficulty": "medium",
        "orig_width": orig_width,
        "orig_height": orig_height,
        "orig_bits_per_pixel": orig_bits_per_pixel,
        "new_width": new_width,
        "new_height": new_height,
        "new_bits_per_pixel": new_bits_per_pixel,
        "images_count": images_count,
        "total_saved_kb": total_saved_kb,
        "units": "KB",
        "condition": condition,
    }
    return params, target_param, answer


@_register("sound_bit_depth")
def _gen_sound_bit_depth() -> tuple[dict[str, Any], str, int]:
    channels = random.choice([1, 2, 4])
    sample_rate_hz = random.choice([240_000, 124_000, 96_000, 64_000])
    bandwidth_kb_per_sec = random.choice([168, 256, 512, 840])
    compression_ratio = random.choice([0.6, 0.7, 0.72, 0.75])

    bandwidth_bits_per_sec = bandwidth_kb_per_sec * 1024 * 8
    effective_bits_per_sec = channels * sample_rate_hz * (1 - compression_ratio)
    bit_depth = math.floor(bandwidth_bits_per_sec / effective_bits_per_sec)

    params = {
        "task_type": "7",
        "kind": "sound",
        "subtype": "sound_bit_depth",
        "difficulty": "hard",
        "channels": channels,
        "sample_rate_hz": sample_rate_hz,
        "bandwidth_kb_per_sec": bandwidth_kb_per_sec,
        "compression_ratio": compression_ratio,
        "units": "bits",
    }
    return params, "bit_depth", bit_depth


@_register("sound_duration")
def _gen_sound_duration() -> tuple[dict[str, Any], str, int]:
    channels = random.choice([1, 2, 4])
    bit_depth = random.choice([8, 12, 16, 18, 24])
    sample_rate_hz = random.choice([44_100, 48_000, 64_000])
    speed_bits_per_sec = random.choice([128_000, 192_000, 204_000, 256_000])

    target_param = random.choice(["duration_sec", "transmit_time_sec"])
    if target_param == "transmit_time_sec":
        duration_sec = random.choice([30, 60, 68, 90, 120])
        total_bits = channels * sample_rate_hz * bit_depth * duration_sec
        transmit_time_sec = math.ceil(total_bits / speed_bits_per_sec)
        answer = transmit_time_sec
        condition = "не менее"
    else:
        transmit_time_sec = random.choice([60, 90, 120, 180])
        duration_sec = int(
            transmit_time_sec * speed_bits_per_sec
            / (channels * sample_rate_hz * bit_depth)
        )
        answer = duration_sec
        condition = "не более"

    params = {
        "task_type": "7",
        "kind": "sound",
        "subtype": "sound_duration",
        "difficulty": "medium",
        "channels": channels,
        "bit_depth": bit_depth,
        "sample_rate_hz": sample_rate_hz,
        "duration_sec": duration_sec,
        "speed_bits_per_sec": speed_bits_per_sec,
        "transmit_time_sec": transmit_time_sec,
        "units": "sec",
        "condition": condition,
    }
    return params, target_param, answer


SUBTYPES_7: list[str] = list(_GENERATORS.keys())


def generate_params_7(subtype: str | None = None) -> tuple[dict[str, Any], str, int]:
    """Генерирует параметры для задачи 7."""

    if subtype is None:
        subtype = random.choice(SUBTYPES_7)
    elif subtype not in _GENERATORS:
        raise ValueError(f"Неподдерживаемый подтип для задания 7: {subtype}")

    params, target_param, answer = _GENERATORS[subtype]()
    params.setdefault("topic", params.get("subtype"))
    return params, target_param, answer


def is_valid_params_7(params: dict[str, Any], target_param: str, answer: int) -> tuple[bool, str]:
    """Проверяет допустимость параметров задания 7."""

    required_common = {"task_type", "subtype", "units"}
    if not required_common.issubset(params.keys()):
        missing = required_common - params.keys()
        return False, f"Отсутствуют обязательные ключи: {missing}"

    subtype = params.get("subtype")
    if subtype not in SUBTYPES_7:
        return False, f"Неизвестный подтип: {subtype}"

    if not isinstance(answer, int) or answer <= 0:
        return False, f"Ответ должен быть положительным целым числом, получено: {answer}"

    if answer > MAX_REFERENCE_ANSWER:
        return False, (
            f"Ответ {answer} превышает максимум {MAX_REFERENCE_ANSWER} "
            f"для подтипа '{subtype}' — параметры сгенерированы некорректно"
        )

    numeric_keys = _get_numeric_keys_7(subtype)
    for key in numeric_keys:
        val = params.get(key)
        if val is None:
            return False, f"Числовой параметр '{key}' отсутствует для подтипа '{subtype}'"
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return False, f"Параметр '{key}' содержит NaN или Inf"
        if isinstance(val, (int, float)) and key not in ("compression_ratio",) and val < 0:
            return False, f"Параметр '{key}' не может быть отрицательным: {val}"

    try:
        recomputed = _recompute_answer_7(subtype, params, target_param)
        if recomputed != answer:
            return False, (
                f"Пересчитанный ответ ({recomputed}) не совпадает "
                f"с заявленным ({answer}) для подтипа '{subtype}'"
            )
    except Exception as e:
        return False, f"Ошибка при пересчёте ответа: {e}"

    return True, ""


def _get_numeric_keys_7(subtype: str) -> list[str]:
    """Возвращает список числовых ключей для подтипа задания 7."""

    mapping: dict[str, list[str]] = {
        "image_size": ["width", "height", "image_size_kb"],
        "colors_count": ["width", "height", "image_size_kb"],
        "sound_self_duration": ["channels", "bit_depth", "sample_rate_hz", "file_size_kb"],
        "packet_size": ["width", "height", "bits_per_pixel", "images_per_packet", "packet_mb"],
        "cards_count": [
            "width", "height", "bits_per_pixel", "compression_ratio",
            "service_overhead_kb", "images_count", "card_capacity_gb", "cards_needed",
        ],
        "traffic_saving": [
            "orig_width", "orig_height", "orig_bits_per_pixel",
            "new_width", "new_height", "new_bits_per_pixel",
            "images_count", "total_saved_kb",
        ],
        "sound_bit_depth": [
            "channels", "sample_rate_hz", "bandwidth_kb_per_sec",
            "compression_ratio", "bit_depth",
        ],
        "sound_duration": [
            "channels", "bit_depth", "sample_rate_hz",
            "duration_sec", "speed_bits_per_sec", "transmit_time_sec",
        ],
    }
    return mapping.get(subtype, [])


def _recompute_answer_7(subtype: str, params: dict, target_param: str) -> int:
    """Пересчитывает ответ для задания 7 на основе параметров."""

    if subtype == "image_size":
        bits_total = params["width"] * params["height"] * params["bits_per_pixel"]
        return int(bits_total / 8 / 1024)

    elif subtype == "colors_count":
        bits_total = params["image_size_kb"] * 1024 * 8
        bits_per_pixel = math.floor(bits_total / (params["width"] * params["height"]))
        return 2 ** bits_per_pixel

    elif subtype == "sound_self_duration":
        bits_total = params["file_size_kb"] * 1024 * 8
        return int(bits_total / (params["channels"] * params["sample_rate_hz"] * params["bit_depth"]))

    elif subtype == "packet_size":
        bytes_per_image = params["width"] * params["height"] * params["bits_per_pixel"] / 8
        if target_param == "packet_mb":
            return math.ceil(bytes_per_image * params["images_per_packet"] / (1024 * 1024))
        else:
            return int(params["packet_mb"] * 1024 * 1024 // bytes_per_image)

    elif subtype == "cards_count":
        bytes_per_image = params["width"] * params["height"] * params["bits_per_pixel"] / 8
        compressed_kb = bytes_per_image * params["compression_ratio"] / 1024
        total_bytes_per_image = (compressed_kb + params["service_overhead_kb"]) * 1024
        card_bytes = params["card_capacity_gb"] * 1024 * 1024 * 1024
        if target_param == "cards_needed":
            return math.ceil(total_bytes_per_image * params["images_count"] / card_bytes)
        else:
            return int(params["cards_needed"] * card_bytes // total_bytes_per_image)

    elif subtype == "traffic_saving":
        orig_bits = params["orig_width"] * params["orig_height"] * params["orig_bits_per_pixel"]
        new_bits = params["new_width"] * params["new_height"] * params["new_bits_per_pixel"]
        saved_kb_per_image = (orig_bits - new_bits) / 8 / 1024
        if target_param == "total_saved_kb":
            return int(saved_kb_per_image * params["images_count"])
        else:
            return math.ceil(params["total_saved_kb"] / saved_kb_per_image)

    elif subtype == "sound_bit_depth":
        bandwidth_bits = params["bandwidth_kb_per_sec"] * 1024 * 8
        effective = params["channels"] * params["sample_rate_hz"] * (1 - params["compression_ratio"])
        return math.floor(bandwidth_bits / effective)

    elif subtype == "sound_duration":
        if target_param == "transmit_time_sec":
            total_bits = (
                    params["channels"] * params["sample_rate_hz"]
                    * params["bit_depth"] * params["duration_sec"]
            )
            return math.ceil(total_bits / params["speed_bits_per_sec"])
        else:
            return int(
                params["transmit_time_sec"] * params["speed_bits_per_sec"]
                / (params["channels"] * params["sample_rate_hz"] * params["bit_depth"])
            )

    raise ValueError(f"Неизвестный подтип для пересчёта: {subtype}")
