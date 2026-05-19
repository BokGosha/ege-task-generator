"""
Интеграционные тесты для GET /api/v1/tasks/history.
Пагинация, фильтры, сортировка по created_at DESC.
"""

import pytest

pytestmark = [pytest.mark.asyncio]


class TestHistoryEndpoint:
    """GET /api/v1/tasks/history"""

    async def test_history_returns_items(self, client):
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})

        resp = await client.get("/api/v1/tasks/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_history_pagination(self, client):
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})
        await client.post("/api/v1/tasks/generate", json={"task_type": 11})

        resp = await client.get("/api/v1/tasks/history?page=1&page_size=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 1
        assert len(data["items"]) == 1

    async def test_history_filter_by_task_type(self, client):
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})

        resp = await client.get("/api/v1/tasks/history?task_type=7")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["task_type"] == 7

    async def test_history_filter_by_status(self, client):
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})

        resp = await client.get("/api/v1/tasks/history?status=accepted")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "accepted"

    async def test_history_item_fields(self, client):
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})

        resp = await client.get("/api/v1/tasks/history")
        item = resp.json()["items"][0]
        assert "task_id" in item
        assert "task_type" in item
        assert "subtype" in item
        assert "status" in item
        assert "created_at" in item
        assert "total_iterations" in item
