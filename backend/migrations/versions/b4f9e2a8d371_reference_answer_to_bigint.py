"""reference_answer to bigint

Revision ID: b4f9e2a8d371
Revises: 1009defd9751
Create Date: 2026-04-08 00:30:00.000000

Расширяет колонку tasks.reference_answer с INTEGER до BIGINT.
Причина: генераторы параметров задач ЕГЭ могут (при регрессиях) выдавать
ответы, превышающие диапазон int32. BIGINT выступает как defence-in-depth
дополнительно к проверке MAX_REFERENCE_ANSWER в is_valid_params_*.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b4f9e2a8d371"
down_revision: Union[str, Sequence[str], None] = "1009defd9751"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Расширяет reference_answer до BIGINT для защиты от переполнения int32."""
    op.alter_column(
        "tasks",
        "reference_answer",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Возвращает INTEGER; значения > 2^31-1 при этом будут обрезаны приведением."""
    op.alter_column(
        "tasks",
        "reference_answer",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="reference_answer::integer",
    )
