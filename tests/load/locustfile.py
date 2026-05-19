"""
Нагрузочный сценарий для генератора заданий ЕГЭ.

Сценарий моделирует целевую нагрузку 10–50 одновременных пользователей,
каждый из которых периодически дёргает ``POST /api/v1/tasks/generate``.

Ожидаемое поведение системы под нагрузкой:
- HTTP 200 — основной успешный ответ.
- HTTP 429 — клиент превысил ``RATE_LIMIT_PER_MINUTE`` (по IP, на воркер).
  Это **не** ошибка теста: rate limit работает, как задумано.
- HTTP 504 / ``LLM_TIMEOUT`` — провайдер LLM не уложился в
  ``LLM_TIMEOUT_SECONDS``; должно быть редким.
- HTTP 5xx — должны быть около нуля.

Запуск (требуется Locust >= 2.20):

    pip install locust
    locust -f tests/load/locustfile.py --host http://localhost:8000

Затем открыть http://localhost:8089 и задать число пользователей и рампу.
"""

import logging
import random

from locust import HttpUser, between, events, task

logger = logging.getLogger(__name__)

TASK_TYPES: list[int] = [7, 11]

GENERATE_ENDPOINT = "/api/v1/tasks/generate"

EXPECTED_STATUS_CODES = {200, 429}


class TaskGeneratorUser(HttpUser):
    """
    Виртуальный пользователь, эмулирующий клиента генератора задач.

    Ждёт между запросами 3–7 секунд, чтобы не упираться сразу в rate limit
    одного клиента (по умолчанию ``RATE_LIMIT_PER_MINUTE=5``). Реальный
    клиент-человек заведомо тратит больше времени между генерациями.
    """

    wait_time = between(3, 7)

    @task
    def generate_task(self) -> None:
        """Один HTTP-запрос на генерацию случайной задачи."""

        task_type = random.choice(TASK_TYPES)
        payload = {"task_type": task_type, "subtype": None}

        with self.client.post(
                GENERATE_ENDPOINT,
                json=payload,
                name=f"{GENERATE_ENDPOINT} (type={task_type})",
                catch_response=True,
        ) as response:
            request_id = response.headers.get("X-Request-ID", "-")

            if response.status_code == 200:
                response.success()
                return

            if response.status_code == 429:
                response.success()
                return

            if response.status_code in (502, 503, 504):
                response.failure(
                    f"upstream/timeout: {response.status_code} "
                    f"request_id={request_id} body={response.text[:200]}"
                )
                return

            response.failure(
                f"unexpected status {response.status_code} "
                f"request_id={request_id} body={response.text[:200]}"
            )


@events.quitting.add_listener
def _check_failure_rate(environment, **_kwargs) -> None:
    """
    Фейлит весь прогон, если доля провалов > 1% или p95 > 180 с.

    Полезно для CI: запуск с ``--headless --exit-code-on-error 1`` вернёт
    ненулевой код, и пайплайн упадёт.
    """

    stats = environment.stats.total
    if stats.num_requests == 0:
        return

    failure_ratio = stats.num_failures / stats.num_requests
    if failure_ratio > 0.01:
        logger.error(
            "Доля ошибок %.2f%% превышает порог 1%%", failure_ratio * 100,
        )
        environment.process_exit_code = 1

    p95 = stats.get_response_time_percentile(0.95)
    if p95 and p95 > 180_000:
        logger.error("p95 %.0f мс превышает порог 180000 мс", p95)
        environment.process_exit_code = 1
