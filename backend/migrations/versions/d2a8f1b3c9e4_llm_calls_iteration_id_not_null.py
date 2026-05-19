"""llm_calls.iteration_id NOT NULL

Revision ID: d2a8f1b3c9e4
Revises: c1d3e4f5a6b7
Create Date: 2026-05-11 12:00:00.000000

Делает llm_calls.iteration_id NOT NULL: в текущем конвейере каждый
вызов LLM всегда привязан к итерации (генерация формулировки или
валидация), поэтому NULL фактически не используется. Приводит схему
в соответствие с реальностью и делает связь со стороны ребёнка 1:1.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2a8f1b3c9e4"
down_revision: Union[str, Sequence[str], None] = "c1d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Переводит llm_calls.iteration_id в NOT NULL."""
    # Подстраховка: если вдруг в таблице есть строки с NULL — удаляем их.
    # В текущем конвейере таких быть не должно, но защищаемся от старых данных.
    op.execute("DELETE FROM llm_calls WHERE iteration_id IS NULL")
    op.alter_column(
        "llm_calls",
        "iteration_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=False,
    )


def downgrade() -> None:
    """Возвращает llm_calls.iteration_id в NULLABLE."""
    op.alter_column(
        "llm_calls",
        "iteration_id",
        existing_type=sa.dialects.postgresql.UUID(),
        nullable=True,
    )
