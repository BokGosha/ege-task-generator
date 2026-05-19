"""
Интеграционные тесты для GET /api/v1/export/tasks/{task_id}.
Форматы: json, txt, pdf.
"""

import pytest
from uuid import uuid4

pytestmark = [pytest.mark.asyncio]


class TestExportEndpoint:
    """GET /api/v1/export/tasks/{task_id}"""

    async def _create_task(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate", json={"task_type": 7},
        )
        return resp.json()["task_id"]

    async def test_export_json(self, client):
        task_id = await self._create_task(client)
        resp = await client.get(f"/api/v1/export/tasks/{task_id}?format=json")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

    async def test_export_txt(self, client):
        task_id = await self._create_task(client)
        resp = await client.get(f"/api/v1/export/tasks/{task_id}?format=txt")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    async def test_export_pdf(self, client):
        task_id = await self._create_task(client)
        resp = await client.get(f"/api/v1/export/tasks/{task_id}?format=pdf")
        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
        assert resp.content[:4] == b"%PDF"

    async def test_export_nonexistent_returns_404(self, client):
        resp = await client.get(f"/api/v1/export/tasks/{uuid4()}?format=json")
        assert resp.status_code == 404
