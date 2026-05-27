"""
Интеграционные тесты записи аудита генерации параметров (ParamGenerationAudit).
"""

import pytest
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.param_generation_audit import ParamGenerationAudit
from backend.app.services.param_generator import _GENERATORS
from backend.app.generators.task7 import generate_params_7, is_valid_params_7

pytestmark = [pytest.mark.asyncio]


class TestParamAuditCreation:
    """Проверяет создание записей аудита при неуспешных попытках генерации параметров."""

    async def test_audit_records_created_on_retry(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        """При retry генерации параметров в БД появляется запись аудита с attempt_number=1."""

        call_count = {"n": 0}

        def patched_validate(params, target_param, answer):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return False, "Первая попытка невалидна (тест)"
            return is_valid_params_7(params, target_param, answer)

        original_gen, original_val, original_subtypes = _GENERATORS[7]

        with patch.dict(
            "backend.app.services.param_generator._GENERATORS",
            {7: (original_gen, patched_validate, original_subtypes)},
        ):
            resp = await client.post(
                "/api/v1/tasks/generate",
                json={"task_type": 7, "subtype": "image_size"},
            )

        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        result = await db_session.execute(
            select(ParamGenerationAudit)
            .where(ParamGenerationAudit.task_id == task_id)
            .order_by(ParamGenerationAudit.attempt_number)
        )
        audits = result.scalars().all()
        assert len(audits) >= 1
        assert audits[0].attempt_number == 1
        assert "невалидна" in audits[0].rejection_reason

    async def test_no_audit_on_first_attempt_success(
        self, client: AsyncClient, db_session: AsyncSession,
    ) -> None:
        """При успешной первой попытке записи аудита не создаются."""

        resp = await client.post(
            "/api/v1/tasks/generate",
            json={"task_type": 7},
        )
        assert resp.status_code == 200

        task_id = resp.json()["task_id"]

        result = await db_session.execute(
            select(ParamGenerationAudit).where(
                ParamGenerationAudit.task_id == task_id,
            )
        )
        audits = result.scalars().all()
        assert len(audits) == 0
