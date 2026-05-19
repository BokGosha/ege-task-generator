"""
Unit-тесты для ParamGeneratorService: retry-логика, кросс-проверка ответа и запись аудита.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.core.exceptions import (
    InvalidTaskTypeError,
    ParamRetryExhaustedError,
)
from backend.app.services import param_generator as pg_module
from backend.app.services.param_generator import ParamGeneratorService

pytestmark = [pytest.mark.asyncio]


def _make_session() -> MagicMock:
    """Создаёт fake-сессию, где add — sync, flush — async."""

    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


class TestParamGeneratorServiceBasics:
    """Базовые проверки валидации входа и happy path."""

    async def test_raises_invalid_task_type_error(self) -> None:
        """task_type вне _GENERATORS вызывает InvalidTaskTypeError."""

        service = ParamGeneratorService()
        session = _make_session()
        task_id = uuid4()

        with pytest.raises(InvalidTaskTypeError) as excinfo:
            await service.generate(session, task_id, task_type=99)

        assert excinfo.value.task_id == task_id
        assert "не поддерживается" in excinfo.value.message
        session.add.assert_not_called()

    async def test_happy_path_returns_params_on_first_attempt(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """При валидном наборе с первой попытки возвращается результат без записей в аудит."""

        fake_params = {"task_type": "7", "subtype": "image_size", "key": 42}
        fake_target = "image_size_kb"
        fake_answer = 123

        fake_gen = MagicMock(return_value=(fake_params, fake_target, fake_answer))
        fake_validate = MagicMock(return_value=(True, ""))
        monkeypatch.setitem(
            pg_module._GENERATORS, 7, (fake_gen, fake_validate, ["image_size"]),
        )
        monkeypatch.setattr(
            pg_module, "calculate_answer", lambda *a, **k: fake_answer,
        )

        service = ParamGeneratorService()
        session = _make_session()
        task_id = uuid4()

        params, target, answer, subtype = await service.generate(
            session, task_id, task_type=7, subtype="image_size",
        )

        assert params is fake_params
        assert target == fake_target
        assert answer == fake_answer
        assert subtype == "image_size"
        session.add.assert_not_called()


class TestParamGeneratorRetryLogic:
    """Retry-цикл: неудачные попытки, audit, исчерпание."""

    async def test_retries_until_valid(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Первые 2 вызова validate_fn отклоняют, третий принимает — в аудит записано 2 строки."""

        good_params = {"task_type": "7", "subtype": "image_size"}
        fake_gen = MagicMock(return_value=(good_params, "image_size_kb", 10))

        validate_calls = {"count": 0}

        def fake_validate(*args, **kwargs):
            validate_calls["count"] += 1
            if validate_calls["count"] < 3:
                return (False, "причина отклонения")
            return (True, "")

        monkeypatch.setitem(
            pg_module._GENERATORS, 7, (fake_gen, fake_validate, ["image_size"]),
        )
        monkeypatch.setattr(pg_module, "calculate_answer", lambda *a, **k: 10)

        service = ParamGeneratorService()
        session = _make_session()
        task_id = uuid4()

        params, target, answer, subtype = await service.generate(
            session, task_id, task_type=7, subtype="image_size",
        )

        assert answer == 10
        assert session.add.call_count == 2
        assert session.flush.await_count == 2

    async def test_exhausts_all_attempts_and_raises(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Все MAX_PARAM_ATTEMPTS попыток отклонены — поднимается ParamRetryExhaustedError."""

        fake_gen = MagicMock(
            return_value=({"task_type": "7", "subtype": "image_size"}, "k", 1),
        )
        fake_validate = MagicMock(return_value=(False, "всегда плохо"))
        monkeypatch.setitem(
            pg_module._GENERATORS, 7, (fake_gen, fake_validate, ["image_size"]),
        )
        monkeypatch.setattr(pg_module, "calculate_answer", lambda *a, **k: 1)

        service = ParamGeneratorService()
        session = _make_session()
        task_id = uuid4()

        with pytest.raises(ParamRetryExhaustedError) as excinfo:
            await service.generate(session, task_id, task_type=7, subtype="image_size")

        assert excinfo.value.task_id == task_id
        assert session.add.call_count == ParamGeneratorService.MAX_PARAM_ATTEMPTS
        assert fake_gen.call_count == ParamGeneratorService.MAX_PARAM_ATTEMPTS

    async def test_cross_check_mismatch_triggers_retry(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Расхождение calculate_answer и ответа генератора отклоняет попытку."""

        fake_gen = MagicMock(
            return_value=({"task_type": "7", "subtype": "image_size"}, "k", 100),
        )
        fake_validate = MagicMock(return_value=(True, ""))
        monkeypatch.setitem(
            pg_module._GENERATORS, 7, (fake_gen, fake_validate, ["image_size"]),
        )
        monkeypatch.setattr(pg_module, "calculate_answer", lambda *a, **k: 999)

        service = ParamGeneratorService()
        session = _make_session()
        task_id = uuid4()

        with pytest.raises(ParamRetryExhaustedError):
            await service.generate(session, task_id, task_type=7, subtype="image_size")

        assert session.add.call_count == ParamGeneratorService.MAX_PARAM_ATTEMPTS
        added_audits = [call.args[0] for call in session.add.call_args_list]
        assert any(
            "Кросс-проверка" in audit.rejection_reason for audit in added_audits
        )

    async def test_value_error_in_generator_is_logged_and_retried(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ValueError из generate_params логируется в аудит и цикл продолжается."""

        good_params = {"task_type": "7", "subtype": "image_size"}
        attempts = {"count": 0}

        def fake_gen(*args, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ValueError("синтетическая ошибка генератора")
            return good_params, "k", 10

        fake_validate = MagicMock(return_value=(True, ""))
        monkeypatch.setitem(
            pg_module._GENERATORS, 7, (fake_gen, fake_validate, ["image_size"]),
        )
        monkeypatch.setattr(pg_module, "calculate_answer", lambda *a, **k: 10)

        service = ParamGeneratorService()
        session = _make_session()
        task_id = uuid4()

        _, _, answer, _ = await service.generate(
            session, task_id, task_type=7, subtype="image_size",
        )

        assert answer == 10
        assert session.add.call_count == 1
        added = session.add.call_args_list[0].args[0]
        assert "Ошибка генерации" in added.rejection_reason

    async def test_audit_records_contain_attempt_number(
            self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """После 3 неудач аудит содержит записи с attempt_number 1, 2, 3."""

        fake_gen = MagicMock(
            return_value=({"task_type": "7", "subtype": "image_size"}, "k", 1),
        )
        validate_calls = {"count": 0}

        def fake_validate(*args, **kwargs):
            validate_calls["count"] += 1
            if validate_calls["count"] <= 3:
                return (False, f"reason-{validate_calls['count']}")
            return (True, "")

        monkeypatch.setitem(
            pg_module._GENERATORS, 7, (fake_gen, fake_validate, ["image_size"]),
        )
        monkeypatch.setattr(pg_module, "calculate_answer", lambda *a, **k: 1)

        service = ParamGeneratorService()
        session = _make_session()
        task_id = uuid4()

        await service.generate(session, task_id, task_type=7, subtype="image_size")

        attempt_numbers = [
            call.args[0].attempt_number for call in session.add.call_args_list
        ]
        assert attempt_numbers == [1, 2, 3]
