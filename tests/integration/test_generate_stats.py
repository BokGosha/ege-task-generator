"""
Тест изоляции конкурентных запросов на генерацию.
Параллельные POST /api/v1/tasks/generate с разными типами (7/11)
должны давать независимые результаты.
"""

import asyncio

import pytest

pytestmark = [pytest.mark.asyncio]


class TestConcurrentRequestIsolation:
    """Параллельные запросы генерации не влияют друг на друга."""

    async def test_parallel_generate_independent_results(self, client):
        """Запускаем несколько генераций параллельно и проверяем изоляцию."""

        async def generate(task_type: int):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": task_type},
            )
            return resp

        results = await asyncio.gather(
            generate(7), generate(11), generate(7), generate(11),
        )

        for resp in results:
            assert resp.status_code == 200, f"Unexpected status: {resp.status_code}"

        data = [r.json() for r in results]

        task_ids = [d["task_id"] for d in data]
        assert len(set(task_ids)) == 4, "task_id должны быть уникальными"

        assert data[0]["task_type"] == 7
        assert data[1]["task_type"] == 11
        assert data[2]["task_type"] == 7
        assert data[3]["task_type"] == 11

        for d in data:
            assert d["parameters"] is not None
            assert d["reference_answer"] is not None
            assert d["status"] in ("accepted", "rejected")

    async def test_parallel_generate_independent_iterations(self, client):
        """Итерации каждого задания принадлежат только ему."""

        async def generate(task_type: int):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": task_type},
            )
            return resp.json()

        results = await asyncio.gather(
            generate(7), generate(11),
        )

        for data in results:
            task_id = data["task_id"]
            resp = await client.get(f"/api/v1/tasks/{task_id}")
            assert resp.status_code == 200
            card = resp.json()

            assert card["task_id"] == task_id
            assert len(card["iterations"]) >= 1
            attempt_nos = [it["attempt_no"] for it in card["iterations"]]
            assert attempt_nos == sorted(attempt_nos)
            assert attempt_nos[0] == 1
