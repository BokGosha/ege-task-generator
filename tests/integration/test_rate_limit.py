"""
Интеграционные тесты rate limiting эндпоинта /generate.
"""

import pytest

from httpx import AsyncClient
from slowapi.wrappers import Limit
from limits import parse as parse_limit

from backend.app.core.rate_limit import limiter

pytestmark = [pytest.mark.asyncio]

_TEST_RATE_LIMIT = 2
_ROUTE_KEY = "backend.app.api.v1.tasks.generate_task"


@pytest.fixture(autouse=True)
def _override_rate_limit():
    """Временно устанавливает строгий лимит (2/min) и фиксирует key_func для тестов."""

    original_limits = limiter._route_limits.get(_ROUTE_KEY, [])
    original_key_func = limiter._key_func

    limiter._key_func = lambda *args, **kwargs: "test-client"

    test_limit = Limit(
        limit=parse_limit(f"{_TEST_RATE_LIMIT}/minute"),
        key_func=lambda *args, **kwargs: "test-client",
        scope="",
        per_method=False,
        methods=None,
        error_message=None,
        exempt_when=None,
        cost=1,
        override_defaults=True,
    )
    limiter._route_limits[_ROUTE_KEY] = [test_limit]

    yield

    limiter._route_limits[_ROUTE_KEY] = original_limits
    limiter._key_func = original_key_func


class TestRateLimitGenerate:
    """Проверяет срабатывание rate limit на /api/v1/tasks/generate."""

    async def test_under_limit_succeeds(self, client: AsyncClient) -> None:
        """Один запрос в рамках лимита проходит с 200 OK."""

        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 7},
        )
        assert resp.status_code == 200

    async def test_exceeds_limit_returns_429(self, client: AsyncClient) -> None:
        """Превышение лимита запросов возвращает HTTP 429."""

        for i in range(_TEST_RATE_LIMIT):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7},
            )
            assert resp.status_code == 200, f"Запрос {i+1} должен пройти"

        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 7},
        )
        assert resp.status_code == 429

    async def test_429_body_has_error_code(self, client: AsyncClient) -> None:
        """Тело 429 содержит code=RATE_LIMIT_EXCEEDED и заголовок Retry-After."""

        for _ in range(_TEST_RATE_LIMIT):
            await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7},
            )

        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 7},
        )
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in resp.headers
