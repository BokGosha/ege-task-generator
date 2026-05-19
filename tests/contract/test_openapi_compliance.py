"""
Контрактные тесты: реальные ответы API валидируются против схем
из openapi.yaml.

Ловят дрейф между объявленным контрактом (YAML) и тем, что
фактически возвращает FastAPI.
"""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft7Validator

from backend.app.main import app

OPENAPI_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend"
    / "app"
    / "resources"
    / "openapi.yaml"
)


def _normalize_nullable(node: Any) -> Any:
    """OpenAPI 3.0 `nullable: true` → JSON Schema `type: [..., "null"]`.

    JSON Schema (Draft 7) не понимает ключ `nullable`. Рекурсивно
    обходим схему и преобразуем формат к совместимому.
    """

    if isinstance(node, dict):
        node = {k: _normalize_nullable(v) for k, v in node.items()}
        if node.pop("nullable", False) and "type" in node:
            t = node["type"]
            if isinstance(t, str) and t != "null":
                node["type"] = [t, "null"]
        return node
    if isinstance(node, list):
        return [_normalize_nullable(item) for item in node]
    return node


def _load_spec() -> dict[str, Any]:
    with open(OPENAPI_PATH, encoding="utf-8") as fh:
        return _normalize_nullable(yaml.safe_load(fh))


OPENAPI_SPEC = _load_spec()


def _resolve_refs(node: Any, seen: frozenset[str] = frozenset()) -> Any:
    """Инлайнит `$ref: '#/...'` ссылки рекурсивно.

    `seen` хранит стек уже разворачиваемых ссылок — при повторной встрече
    возвращаем заглушку, чтобы не уйти в бесконечную рекурсию на циклах.
    """

    if isinstance(node, dict):
        if "$ref" in node and isinstance(node["$ref"], str) and node["$ref"].startswith("#/"):
            ref = node["$ref"]
            if ref in seen:
                return {}
            target: Any = OPENAPI_SPEC
            for part in ref[2:].split("/"):
                target = target[part]
            return _resolve_refs(target, seen | {ref})
        return {k: _resolve_refs(v, seen) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(item, seen) for item in node]
    return node


def _response_schema(path: str, method: str, status: str = "200") -> dict[str, Any]:
    """Извлекает JSON-схему тела ответа из контракта с разрешёнными $ref."""

    operation = OPENAPI_SPEC["paths"][path][method.lower()]
    schema = operation["responses"][status]["content"]["application/json"]["schema"]
    return _resolve_refs(deepcopy(schema))


def _assert_matches(schema: dict[str, Any], payload: Any) -> None:
    """Падает, если payload не соответствует схеме из контракта."""

    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        formatted = "\n".join(
            f"  - {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in errors
        )
        raise AssertionError(f"Ответ нарушает контракт:\n{formatted}")


class TestOpenAPISpecIntegrity:
    """Структурный дрейф между YAML-контрактом и FastAPI runtime."""

    def test_all_yaml_paths_implemented(self) -> None:
        """Каждый путь из openapi.yaml реализован в FastAPI."""

        runtime = app.openapi()
        runtime_paths = set(runtime["paths"].keys())
        yaml_paths = set(OPENAPI_SPEC["paths"].keys())
        missing = yaml_paths - runtime_paths
        assert not missing, f"Пути из контракта отсутствуют в API: {missing}"

    def test_all_yaml_operations_implemented(self) -> None:
        """Каждая пара (path, method) из контракта реализована."""

        runtime = app.openapi()
        for path, methods in OPENAPI_SPEC["paths"].items():
            for method in methods:
                assert method in runtime["paths"].get(path, {}), (
                    f"{method.upper()} {path} объявлен в YAML, но не реализован"
                )


class TestGenerateContract:
    """POST /api/v1/tasks/generate — ответы соответствуют контракту."""

    pytestmark = [pytest.mark.asyncio]

    async def test_success_response_matches_schema(self, client) -> None:
        resp = await client.post("/api/v1/tasks/generate", json={"task_type": 7})
        assert resp.status_code == 200
        _assert_matches(_response_schema("/api/v1/tasks/generate", "post", "200"), resp.json())

    async def test_type_11_success_matches_schema(self, client) -> None:
        resp = await client.post("/api/v1/tasks/generate", json={"task_type": 11})
        assert resp.status_code == 200
        _assert_matches(_response_schema("/api/v1/tasks/generate", "post", "200"), resp.json())

    async def test_invalid_task_type_matches_error_schema(self, client) -> None:
        resp = await client.post("/api/v1/tasks/generate", json={"task_type": 999})
        assert resp.status_code == 400
        _assert_matches(_response_schema("/api/v1/tasks/generate", "post", "400"), resp.json())

    async def test_schema_error_matches_422_schema(self, client) -> None:
        resp = await client.post("/api/v1/tasks/generate", json={"task_type": "seven"})
        assert resp.status_code == 422
        _assert_matches(_response_schema("/api/v1/tasks/generate", "post", "422"), resp.json())


class TestTasksReadContract:
    """GET /api/v1/tasks, /api/v1/tasks/{id}, /api/v1/tasks/history."""

    pytestmark = [pytest.mark.asyncio]

    async def test_task_card_matches_schema(self, client) -> None:
        created = await client.post("/api/v1/tasks/generate", json={"task_type": 7})
        task_id = created.json()["task_id"]

        resp = await client.get(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200
        _assert_matches(_response_schema("/api/v1/tasks/{task_id}", "get", "200"), resp.json())

    async def test_task_list_matches_schema(self, client) -> None:
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200
        _assert_matches(_response_schema("/api/v1/tasks", "get", "200"), resp.json())

    async def test_history_matches_schema(self, client) -> None:
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})
        resp = await client.get("/api/v1/tasks/history")
        assert resp.status_code == 200
        _assert_matches(_response_schema("/api/v1/tasks/history", "get", "200"), resp.json())


class TestStatisticsContract:
    """GET /api/v1/statistics — ответ и ошибка диапазона дат."""

    pytestmark = [pytest.mark.asyncio]

    async def test_statistics_matches_schema(self, client) -> None:
        await client.post("/api/v1/tasks/generate", json={"task_type": 7})
        resp = await client.get("/api/v1/statistics")
        assert resp.status_code == 200
        _assert_matches(_response_schema("/api/v1/statistics", "get", "200"), resp.json())

    async def test_invalid_date_range_matches_error_schema(self, client) -> None:
        resp = await client.get(
            "/api/v1/statistics?from=2099-01-01T00:00:00&to=2020-01-01T00:00:00"
        )
        assert resp.status_code == 400
        _assert_matches(_response_schema("/api/v1/statistics", "get", "400"), resp.json())
