"""
Покрытие:
- POST /api/v1/tasks/generate → ответ, структура, итерации ASC
- POST с неверным Content-Type → 415 или 422
- Ошибки: невалидный тип, формат
- GET /api/v1/statistics?from=...&to=... → аналитика, top-5, ratios
- GET /api/v1/statistics with from > to → 400

CRUD-эндпоинты (GET tasks/{id}, GET tasks, GET history, GET export)
покрыты в test_tasks_crud.py, test_history.py, test_export.py.
"""

import pytest

pytestmark = [pytest.mark.asyncio]


class TestGenerateEndpoint:
    """POST /api/v1/tasks/generate"""

    async def test_generate_returns_200_with_structure(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 7},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "task_id" in data
        assert data["task_type"] == 7
        assert "subtype" in data and data["subtype"] is not None
        assert data["status"] in ("accepted", "rejected")
        assert isinstance(data["reference_answer"], int)
        assert "parameters" in data
        assert "quality_profile" in data
        assert "iterations" in data
        assert "created_at" in data

    async def test_generate_iterations_sorted_asc(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 7},
        )
        data = resp.json()
        iterations = data["iterations"]
        assert len(iterations) >= 1

        attempt_nos = [it["attempt_no"] for it in iterations]
        assert attempt_nos == sorted(attempt_nos), "Итерации должны быть в порядке attempt_no ASC"

    async def test_generate_quality_profile_structure(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 11},
        )
        data = resp.json()
        qp = data["quality_profile"]
        assert qp is not None

        for criterion in ("clarity", "unambiguity", "consistency", "answer_format", "language_correctness"):
            assert criterion in qp
            assert "pass" in qp[criterion]
            assert isinstance(qp[criterion]["pass"], bool)

        assert "verdict" in qp
        assert qp["verdict"] in ("accepted", "rejected")

    async def test_generate_type_11(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 11},
        )
        assert resp.status_code == 200
        assert resp.json()["task_type"] == 11

    async def test_generate_with_explicit_subtype(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 7, "subtype": "image_size"},
        )
        assert resp.status_code == 200
        assert resp.json()["subtype"] == "image_size"


class TestGenerateErrors:
    """Ошибки генерации."""

    async def test_invalid_task_type_returns_400(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 999},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "INVALID_TASK_TYPE"

    async def test_invalid_subtype_returns_400(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 7, "subtype": "nonexistent"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_SUBTYPE"

    async def test_schema_error_returns_422(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": "seven"},
        )
        assert resp.status_code == 422

    async def test_non_json_content_type(self, client):
        resp = await client.post(
            "/api/v1/tasks/generate",
            content="task_type=7",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code in (415, 422)


class TestStatistics:
    """GET /api/v1/statistics"""

    async def test_statistics_structure(self, client):
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})

        resp = await client.get("/api/v1/statistics")
        assert resp.status_code == 200
        data = resp.json()

        assert "total_tasks" in data
        assert data["total_tasks"] >= 1
        assert "status_shares" in data
        shares = data["status_shares"]
        assert "accepted" in shares
        assert "rejected" in shares
        assert "error" in shares
        assert "avg_iterations" in data
        assert "top_rejection_reasons" in data
        assert "by_task_type" in data
        assert "model_stats" in data

    async def test_statistics_with_date_filters(self, client):
        resp = await client.get(
            "/api/v1/statistics?from=2020-01-01T00:00:00&to=2099-12-31T23:59:59"
        )
        assert resp.status_code == 200

    async def test_statistics_invalid_date_range_returns_400(self, client):
        resp = await client.get(
            "/api/v1/statistics?from=2099-01-01T00:00:00&to=2020-01-01T00:00:00"
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "INVALID_DATE_RANGE"

    async def test_statistics_status_ratios_sum(self, client):
        resp = await client.get("/api/v1/statistics")
        data = resp.json()
        shares = data["status_shares"]
        total = shares["accepted"] + shares["rejected"] + shares["error"]
        assert abs(total - 1.0) < 0.01 or data["total_tasks"] == 0
