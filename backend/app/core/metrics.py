"""Prometheus-метрики для наблюдаемости конвейера генерации."""

from prometheus_client import Counter, Histogram

tasks_generated_total = Counter(
    "tasks_generated_total",
    "Общее количество сгенерированных заданий",
    ["task_type", "status"],
)

llm_calls_total = Counter(
    "llm_calls_total",
    "Общее количество LLM-вызовов",
    ["call_type", "provider", "status"],
)

task_generation_duration_seconds = Histogram(
    "task_generation_duration_seconds",
    "Длительность полного цикла генерации задания в секундах",
    buckets=(1, 5, 10, 30, 60, 90, 120, 180, 300),
)
