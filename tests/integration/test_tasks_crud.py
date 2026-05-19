"""
Интеграционные тесты для GET /api/v1/tasks/{task_id} и GET /api/v1/tasks.
"""

from uuid import uuid4

import pytest

pytestmark = [pytest.mark.asyncio]


class TestGetTaskById:
    """GET /api/v1/tasks/{task_id}"""

    async def test_get_existing_task(self, client):
        gen = await client.post("/api/v1/tasks/generate", json={"task_type": 7})
        task_id = gen.json()["task_id"]

        resp = await client.get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == task_id
        assert data["task_type"] == 7
        assert data["status"] in ("accepted", "rejected")

    async def test_get_nonexistent_returns_404(self, client):
        resp = await client.get(f"/api/v1/tasks/{uuid4()}")
        assert resp.status_code == 404

    async def test_404_has_error_body(self, client):
        resp = await client.get(f"/api/v1/tasks/{uuid4()}")
        body = resp.json()
        assert "detail" in body or "error" in body.get("detail", {})


class TestGetTasksList:
    """GET /api/v1/tasks"""

    async def test_list_returns_items(self, client):
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})

        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_date_filters_inclusive(self, client):
        gen = await client.post("/api/v1/tasks/generate", json={"task_type": 7})
        created_at = gen.json()["created_at"]

        resp = await client.get(
            f"/api/v1/tasks?created_from={created_at}&created_to={created_at}"
        )
        assert resp.status_code == 200

    async def test_list_short_card_fields(self, client):
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})

        resp = await client.get("/api/v1/tasks")
        item = resp.json()["items"][0]
        assert "task_id" in item
        assert "task_type" in item
        assert "subtype" in item
        assert "status" in item
        assert "created_at" in item
