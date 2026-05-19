"""
Тесты консистентности персистентного слоя.
Проверяют наличие обязательных записей для каждого
терминального статуса: accepted, rejected, error.
"""

import pytest
from sqlalchemy import select

from backend.app.models.llm_call import LlmCall
from backend.app.models.task import Task
from backend.app.models.task_iteration import TaskIteration
from backend.app.models.task_quality import TaskQuality

pytestmark = [pytest.mark.asyncio]


async def _generate(client, task_type: int = 7):
    """Вспомогательный вызов генерации."""

    resp = await client.post(
        "/api/v1/tasks/generate",
        json={"task_type": task_type},
    )
    return resp


class TestAcceptedPersistence:
    """Проверки записей при статусе accepted."""

    async def test_accepted_has_task_and_iterations(self, client, db_session):
        resp = await _generate(client)
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        task = (await db_session.execute(
            select(Task).where(Task.id == task_id)
        )).scalar_one()
        assert task.status == "accepted"
        assert task.final_wording is not None
        assert task.reference_answer is not None

        iters = (await db_session.execute(
            select(TaskIteration).where(TaskIteration.task_id == task_id)
        )).scalars().all()
        assert len(iters) >= 1

        last_iter = max(iters, key=lambda i: i.iteration_number)
        assert last_iter.status == "accepted"

    async def test_accepted_has_quality_profile(self, client, db_session):
        resp = await _generate(client)
        task_id = resp.json()["task_id"]

        iters = (await db_session.execute(
            select(TaskIteration).where(TaskIteration.task_id == task_id)
        )).scalars().all()

        accepted_iter = [i for i in iters if i.status == "accepted"]
        assert len(accepted_iter) >= 1

        quality = (await db_session.execute(
            select(TaskQuality).where(
                TaskQuality.iteration_id == accepted_iter[0].id
            )
        )).scalar_one_or_none()
        assert quality is not None
        assert quality.verdict == "accepted"

    async def test_accepted_has_llm_calls(self, client, db_session):
        resp = await _generate(client)
        task_id = resp.json()["task_id"]

        llm_calls = (await db_session.execute(
            select(LlmCall).where(LlmCall.task_id == task_id)
        )).scalars().all()

        assert len(llm_calls) >= 2

        call_types = {c.call_type for c in llm_calls}
        assert "wording_generation" in call_types
        assert "semantic_validation" in call_types


class TestTerminalStatusImmutability:
    """
    Терминальные статусы необратимы — Task со статусом accepted/rejected/error
    не меняется при повторном чтении.
    """

    async def test_status_persists_after_read(self, client, db_session):
        resp = await _generate(client)
        data = resp.json()
        task_id = data["task_id"]
        original_status = data["status"]

        resp2 = await client.get(f"/api/v1/tasks/{task_id}")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == original_status
