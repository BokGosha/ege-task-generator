"""llm_calls estimated_cost_usd to rub

Revision ID: c1d3e4f5a6b7
Revises: b4f9e2a8d371
Create Date: 2026-04-18 12:00:00.000000

Переименовывает колонку llm_calls.estimated_cost_usd в estimated_cost_rub:
YandexGPT и GigaChat тарифицируются в рублях, USD не соответствует реальности.
Данные сохраняются (rename колонки, не пересоздание).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c1d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b4f9e2a8d371"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Переименовывает estimated_cost_usd → estimated_cost_rub."""
    op.alter_column(
        "llm_calls",
        "estimated_cost_usd",
        new_column_name="estimated_cost_rub",
    )


def downgrade() -> None:
    """Возвращает имя estimated_cost_usd."""
    op.alter_column(
        "llm_calls",
        "estimated_cost_rub",
        new_column_name="estimated_cost_usd",
    )
