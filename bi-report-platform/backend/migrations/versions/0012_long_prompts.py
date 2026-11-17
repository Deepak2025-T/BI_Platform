"""prompts and questions as unbounded text

A report is often asked for with a whole specification pasted in - every tab, its KPIs and its
charts - and VARCHAR(2000) refused exactly those requests. Widening only ever accepts more, so
there is nothing to convert and no data can be lost going up.

Revision ID: 0012_long_prompts
Revises: 0011_report_shares
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0012_long_prompts'
down_revision: Union[str, None] = '0011_report_shares'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [('reports', 'prompt'), ('report_templates', 'prompt'), ('chat_messages', 'question')]


def upgrade() -> None:
    if _is_sqlite():
        return  # SQLite does not enforce VARCHAR lengths, so these columns already hold any length.
    for table, column in _COLUMNS:
        op.alter_column(table, column, type_=sa.Text(), existing_type=sa.String(length=2000),
                        existing_nullable=False)


def downgrade() -> None:
    if _is_sqlite():
        return
    # Anything written since the upgrade may be longer than 2000, so trim before narrowing or the
    # column change itself fails.
    for table, column in _COLUMNS:
        op.execute(sa.text(f'UPDATE {table} SET {column} = substr({column}, 1, 2000) '
                           f'WHERE length({column}) > 2000'))
        op.alter_column(table, column, type_=sa.String(length=2000), existing_type=sa.Text(),
                        existing_nullable=False)


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"
