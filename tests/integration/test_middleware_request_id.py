"""
Интеграционные тесты middleware X-Request-ID.
"""

import uuid

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.asyncio]


class TestRequestIdMiddleware:
    """Проверяет RequestIDMiddleware на эхо и генерацию request_id."""

    async def test_echo_provided_request_id(self, client: AsyncClient) -> None:
        """Переданный X-Request-ID эхом возвращается в ответе."""

        custom_id = "test-req-" + str(uuid.uuid4())
        resp = await client.get(
            "/health",
            headers={"X-Request-ID": custom_id},
        )
        assert resp.status_code == 200
        assert resp.headers["X-Request-ID"] == custom_id

    async def test_generates_request_id_when_not_provided(self, client: AsyncClient) -> None:
        """Если X-Request-ID не передан, сервер генерирует валидный UUID."""

        resp = await client.get("/health")
        assert resp.status_code == 200
        returned_id = resp.headers.get("X-Request-ID")
        assert returned_id is not None
        uuid.UUID(returned_id)
