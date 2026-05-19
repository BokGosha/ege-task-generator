"""Бенчмарк ParamGeneratorService: время и память по числу попыток r.

Запуск из корня проекта:
    python -m tests.load.bench_param_generator

Особенности замера:
  - Скрипт принудительно проваливает первые r-1 попыток валидации,
    чтобы зафиксировать ровно r итераций цикла внутри generate().
  - Реальная БД не используется (сессия — async-заглушка), поэтому одна
    попытка стоит порядка единиц микросекунд, что лежит на пределе
    разрешения системного таймера. Для устойчивого измерения применяется
    батч-таймирование: одно измерение = время BATCH_SIZE последовательных
    вызовов, делённое на BATCH_SIZE. Итоговое значение — среднее по
    NUM_BATCHES таких измерений.
  - Память измеряется отдельным прогоном через tracemalloc, чтобы не
    искажать тайминг.
"""

import asyncio
import logging
import statistics
import time
import tracemalloc
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from backend.app.services import param_generator as pg_module
from backend.app.services.param_generator import ParamGeneratorService

logging.getLogger("backend.app.services.param_generator").setLevel(logging.ERROR)

BATCH_SIZE = 2000     # вызовов в одном измерении
NUM_BATCHES = 50      # независимых измерений на одну точку r
WARMUP_BATCHES = 5    # прогревочных батчей (не учитываются)

SUBTYPE = "sound_self_duration"
TASK_TYPE = 7


def _make_session() -> MagicMock:
    """Заглушка AsyncSession: add — no-op, flush — async no-op."""
    session = MagicMock()
    session.add = MagicMock(return_value=None)
    session.flush = AsyncMock(return_value=None)
    return session


async def _measure_for_r(r: int) -> tuple[float, int]:
    """Возвращает (среднее время одного вызова в мкс, пиковая память в байтах)."""
    service = ParamGeneratorService()
    session = _make_session()
    task_id = uuid4()

    # ВАЖНО: param_generator._GENERATORS захватывает ссылку на is_valid_params_7
    # на этапе импорта. Подмена task7.is_valid_params_7 на это уже не влияет —
    # надо переписывать сам словарь _GENERATORS.
    original_entry = pg_module._GENERATORS[TASK_TYPE]
    original_gen, original_validate, original_subtypes = original_entry
    counter = {"n": 0}

    def fake_validate(params, target_param, answer):
        # Первые r-1 попыток валим принудительно, последнюю валидируем по-настоящему.
        counter["n"] += 1
        if counter["n"] < r:
            return False, "forced fail (бенчмарк)"
        return original_validate(params, target_param, answer)

    pg_module._GENERATORS[TASK_TYPE] = (original_gen, fake_validate, original_subtypes)
    try:
        async def run_batch() -> float:
            """Выполняет BATCH_SIZE вызовов и возвращает средн. время одного, мкс."""
            t0 = time.perf_counter()
            for _ in range(BATCH_SIZE):
                counter["n"] = 0
                await service.generate(session, task_id, TASK_TYPE, SUBTYPE)
            elapsed = time.perf_counter() - t0
            return elapsed * 1_000_000.0 / BATCH_SIZE

        # Прогрев.
        for _ in range(WARMUP_BATCHES):
            await run_batch()

        # Замер.
        per_call_us: list[float] = []
        for _ in range(NUM_BATCHES):
            per_call_us.append(await run_batch())

        # Пиковая память — отдельный прогон.
        tracemalloc.start()
        counter["n"] = 0
        await service.generate(session, task_id, TASK_TYPE, SUBTYPE)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    finally:
        pg_module._GENERATORS[TASK_TYPE] = original_entry

    return statistics.fmean(per_call_us), peak_bytes


async def main() -> None:
    print(
        f"Бенчмарк ParamGeneratorService "
        f"(subtype={SUBTYPE}, батч={BATCH_SIZE}×{NUM_BATCHES}, "
        f"прогрев={WARMUP_BATCHES} батчей)"
    )
    print(f"{'r':>3} | {'avg, мкс':>10} | {'peak, KB':>10}")
    print("-" * 32)
    for r in range(1, ParamGeneratorService.MAX_PARAM_ATTEMPTS + 1):
        avg_us, peak_bytes = await _measure_for_r(r)
        print(f"{r:>3} | {avg_us:>10.3f} | {peak_bytes / 1024:>10.2f}")


if __name__ == "__main__":
    asyncio.run(main())
