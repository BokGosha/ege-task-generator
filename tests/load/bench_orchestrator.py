"""Бенчмарк TaskOrchestrator: время и память по числу LLM-итераций m.

Запуск из корня проекта:
    python -m tests.load.bench_orchestrator

Полный TaskOrchestrator.execute() требует поднятой БД и LLM-провайдера, поэтому
бенчится **изолированный эквивалент** цикла _run_pipeline: m итераций, каждая
из которых состоит из вызова генерирующей и валидирующей LLM с фиксированной
задержкой LLM_DELAY_MS (имитация MockLlmAdapter, см. раздел 1.X.2 ПЗ).

Каждая итерация добавляет запись в список history (эквивалент TaskIteration),
что демонстрирует O(m) ёмкостной сложности.
"""

import asyncio
import statistics
import time
import tracemalloc

# Параметры эксперимента (соответствуют разделу 1.X.2 ПЗ).
RUNS_PER_M = 200
WARMUP = 20
LLM_DELAY_MS = 50           # фиксированная задержка одного вызова заглушки
MAX_LLM_ITERATIONS = 3      # см. backend/app/services/task_orchestrator.py:43


async def _mock_llm_call() -> str:
    """Заглушка одного вызова LLM (генератор либо валидатор)."""
    await asyncio.sleep(LLM_DELAY_MS / 1000.0)
    return "stub-wording"


async def _run_pipeline(m: int) -> list[dict]:
    """Эмулирует тело TaskOrchestrator._run_pipeline для m итераций."""
    # Имитация работы param_generator (≈ константа, эквивалент r=1).
    _ = sum(i * i for i in range(1000))

    history: list[dict] = []  # эквивалент TaskIteration → растёт линейно по m
    for iter_num in range(1, m + 1):
        wording = await _mock_llm_call()    # генерация формулировки
        verdict = await _mock_llm_call()    # семантическая валидация
        history.append(
            {
                "iteration_number": iter_num,
                "wording": wording,
                "verdict": verdict,
            }
        )
    return history


async def _measure_for_m(m: int) -> tuple[float, int]:
    """Возвращает (среднее время в мс, пиковая память в байтах) для фикс. m."""
    # Прогрев.
    for _ in range(WARMUP):
        await _run_pipeline(m)

    # Замер времени.
    samples_ms: list[float] = []
    for _ in range(RUNS_PER_M):
        t0 = time.perf_counter()
        await _run_pipeline(m)
        samples_ms.append((time.perf_counter() - t0) * 1000.0)

    # Замер пиковой памяти (отдельный прогон, чтобы не искажать тайминги).
    tracemalloc.start()
    await _run_pipeline(m)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return statistics.fmean(samples_ms), peak_bytes


async def main() -> None:
    print(
        f"Бенчмарк TaskOrchestrator "
        f"(LLM_DELAY={LLM_DELAY_MS} мс, прогонов={RUNS_PER_M}, прогрев={WARMUP})"
    )
    print(f"{'m':>3} | {'avg, мс':>10} | {'peak, KB':>10}")
    print("-" * 32)
    for m in range(1, MAX_LLM_ITERATIONS + 1):
        avg_ms, peak_bytes = await _measure_for_m(m)
        print(f"{m:>3} | {avg_ms:>10.3f} | {peak_bytes / 1024:>10.2f}")


if __name__ == "__main__":
    asyncio.run(main())
