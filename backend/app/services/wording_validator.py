"""Сервис семантической валидации формулировки задания через LLM."""

import logging
import time
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import LlmTimeoutError, LlmValidationError
from backend.app.services.llm_adapter import BaseLlmAdapter
from backend.app.services.llm_logger import log_llm_call
from backend.app.services.prompt_loader import load_prompt, render

logger = logging.getLogger(__name__)

_VALIDATION_SCHEMA = {
    "type": "object",
    "required": [
        "clarity_pass", "clarity_message",
        "unambiguity_pass", "unambiguity_message",
        "consistency_pass", "consistency_message",
        "answer_format_pass", "answer_format_message",
        "language_correctness_pass", "language_correctness_message",
    ],
    "properties": {
        "clarity_pass": {"type": "boolean"},
        "clarity_message": {"type": "string"},
        "unambiguity_pass": {"type": "boolean"},
        "unambiguity_message": {"type": "string"},
        "consistency_pass": {"type": "boolean"},
        "consistency_message": {"type": "string"},
        "answer_format_pass": {"type": "boolean"},
        "answer_format_message": {"type": "string"},
        "language_correctness_pass": {"type": "boolean"},
        "language_correctness_message": {"type": "string"},
    },
}


@dataclass
class ValidationResult:
    """Результат валидации формулировки по 5 булевым критериям."""

    clarity_pass: bool
    clarity_message: Optional[str]
    unambiguity_pass: bool
    unambiguity_message: Optional[str]
    consistency_pass: bool
    consistency_message: Optional[str]
    answer_format_pass: bool
    answer_format_message: Optional[str]
    language_correctness_pass: bool
    language_correctness_message: Optional[str]

    @property
    def is_accepted(self) -> bool:
        """Формулировка принята, если все 5 критериев пройдены."""

        return all([
            self.clarity_pass,
            self.unambiguity_pass,
            self.consistency_pass,
            self.answer_format_pass,
            self.language_correctness_pass,
        ])

    @property
    def verdict(self) -> str:
        return "accepted" if self.is_accepted else "rejected"

    @property
    def diagnostic_message(self) -> Optional[str]:
        """Диагностическое сообщение с перечислением проблем."""

        if self.is_accepted:
            return "Формулировка пригодна."
        failed = self.failed_criteria()
        descriptions = [f"- {name}: {msg}" for name, msg in failed]
        return "Формулировка не прошла проверку:\n" + "\n".join(descriptions)

    def failed_criteria(self) -> list[tuple[str, str]]:
        """Возвращает список (criterion_name, message) для непройденных критериев."""

        result = []
        checks = [
            ("clarity", self.clarity_pass, self.clarity_message),
            ("unambiguity", self.unambiguity_pass, self.unambiguity_message),
            ("consistency", self.consistency_pass, self.consistency_message),
            ("answer_format", self.answer_format_pass, self.answer_format_message),
            ("language_correctness", self.language_correctness_pass, self.language_correctness_message),
        ]
        for name, passed, message in checks:
            if not passed:
                result.append((name, message or "Критерий не пройден"))
        return result

    def feedback_text(self) -> str:
        """Текст обратной связи для повторной генерации формулировки."""

        failed = self.failed_criteria()
        if not failed:
            return ""
        lines = [f"Критерий '{name}': {msg}" for name, msg in failed]
        return "\n".join(lines)


class WordingValidator:
    """Семантическая валидация формулировки задания через LLM."""

    def __init__(self, adapter: BaseLlmAdapter) -> None:
        self._adapter = adapter

    async def validate(
            self,
            session: AsyncSession,
            task_id: UUID,
            iteration_id: UUID,
            task_type: int,
            subtype: str,
            wording: str,
            reference_answer: int,
    ) -> ValidationResult:
        """Валидирует формулировку задания по 5 критериям."""

        prompt = self._build_prompt(
            task_type, subtype, wording, reference_answer,
        )

        request_payload = {
            "prompt": prompt[:500],
            "task_type": task_type,
            "subtype": subtype,
        }
        start = time.monotonic()

        try:
            raw_result = await self._adapter.generate_json(prompt, _VALIDATION_SCHEMA)
            duration_ms = int((time.monotonic() - start) * 1000)

            token_usage = self._adapter.last_token_usage or {}

            await log_llm_call(
                session,
                task_id=task_id,
                iteration_id=iteration_id,
                call_type="semantic_validation",
                provider=self._adapter.provider,
                model_name=self._adapter.model_name,
                request_payload=request_payload,
                response_payload=raw_result,
                status="success",
                prompt_tokens=token_usage.get("prompt_tokens"),
                completion_tokens=token_usage.get("completion_tokens"),
                duration_ms=duration_ms,
            )

            try:
                return self._parse_result(raw_result)
            except LlmValidationError as parse_exc:
                logger.error(
                    "Не удалось распарсить ответ LLM-валидатора (%s): %s; raw=%r",
                    self._adapter.provider, parse_exc, raw_result,
                )
                raise LlmValidationError(parse_exc.message, task_id=task_id) from parse_exc

        except LlmValidationError:
            raise
        except LlmTimeoutError as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error("Таймаут при валидации формулировки: %s", e)

            await log_llm_call(
                session,
                task_id=task_id,
                iteration_id=iteration_id,
                call_type="semantic_validation",
                provider=self._adapter.provider,
                model_name=self._adapter.model_name,
                request_payload=request_payload,
                response_payload=None,
                status="error",
                error_message=str(e),
                duration_ms=duration_ms,
            )

            raise LlmTimeoutError(e.message, task_id=task_id) from e
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error("Ошибка валидации формулировки: %s", e)

            await log_llm_call(
                session,
                task_id=task_id,
                iteration_id=iteration_id,
                call_type="semantic_validation",
                provider=self._adapter.provider,
                model_name=self._adapter.model_name,
                request_payload=request_payload,
                response_payload=None,
                status="error",
                error_message=str(e),
                duration_ms=duration_ms,
            )

            raise LlmValidationError(
                "Не удалось выполнить семантическую валидацию формулировки.",
                task_id=task_id,
            ) from e

    def _parse_result(self, raw: dict) -> ValidationResult:
        """Парсит ответ LLM в ValidationResult.

        Fail-closed: отсутствующие поля считаются непройденными, чтобы
        битый ответ LLM не пропускал задачу автоматически.
        """

        if not isinstance(raw, dict):
            raise LlmValidationError(
                "LLM-валидатор вернул ответ неожиданного формата."
            )

        required_pass_fields = [
            "clarity_pass",
            "unambiguity_pass",
            "consistency_pass",
            "answer_format_pass",
            "language_correctness_pass",
        ]

        if not any(field in raw for field in required_pass_fields):
            for value in raw.values():
                if isinstance(value, dict) and any(
                        field in value for field in required_pass_fields
                ):
                    raw = value
                    break

        if not any(field in raw for field in required_pass_fields):
            raise LlmValidationError(
                "LLM-валидатор вернул ответ без обязательных полей критериев."
            )

        _EMPTY_MSG_TOKENS = {
            "", "ok", "ок", "всё ок", "все ок", "всё понятно", "все понятно",
            "ошибок нет", "нет замечаний", "без замечаний", "нет проблем",
            "n/a", "null", "none",
        }

        def _bool(field: str) -> bool:
            return raw.get(field) is True

        def _raw_message(field: str) -> str:
            msg = raw.get(field)
            return msg.strip() if isinstance(msg, str) else ""

        def _is_meaningful(msg: str) -> bool:
            return msg.lower() not in _EMPTY_MSG_TOKENS and len(msg) >= 8

        def _pass_with_message(pass_field: str, msg_field: str) -> tuple[bool, str]:
            passed = _bool(pass_field)
            msg = _raw_message(msg_field)
            if passed and not _is_meaningful(msg):
                return False, (
                    "Критерий помечен как пройденный, но валидатор не "
                    "привёл обоснования — проверь формулировку."
                )
            if not passed and not msg:
                return False, "Критерий не оценён валидатором."
            return passed, msg

        clarity_pass, clarity_msg = _pass_with_message("clarity_pass", "clarity_message")
        unambiguity_pass, unambiguity_msg = _pass_with_message(
            "unambiguity_pass", "unambiguity_message",
        )
        consistency_pass, consistency_msg = _pass_with_message(
            "consistency_pass", "consistency_message",
        )
        answer_format_pass, answer_format_msg = _pass_with_message(
            "answer_format_pass", "answer_format_message",
        )
        language_correctness_pass, language_correctness_msg = _pass_with_message(
            "language_correctness_pass", "language_correctness_message",
        )

        return ValidationResult(
            clarity_pass=clarity_pass,
            clarity_message=clarity_msg or None,
            unambiguity_pass=unambiguity_pass,
            unambiguity_message=unambiguity_msg or None,
            consistency_pass=consistency_pass,
            consistency_message=consistency_msg or None,
            answer_format_pass=answer_format_pass,
            answer_format_message=answer_format_msg or None,
            language_correctness_pass=language_correctness_pass,
            language_correctness_message=language_correctness_msg or None,
        )

    def _build_prompt(
            self,
            task_type: int,
            subtype: str,
            wording: str,
            reference_answer: int,
    ) -> str:
        """Формирует строгий промпт для LLM-валидатора из декларативного шаблона."""

        return render(
            load_prompt("wording_validator.tmpl"),
            task_type=task_type,
            subtype=subtype,
            wording=wording,
            reference_answer=reference_answer,
        )
