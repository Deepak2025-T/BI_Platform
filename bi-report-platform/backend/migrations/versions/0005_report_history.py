"""report history: how long each report keeps its snapshots, and a small summary per snapshot

Revision ID: 0005_report_history
Revises: 0004_report_refresh
Create Date: 2026-10-23 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005_report_history'
down_revision: Union[str, None] = '0004_report_refresh'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('history_days', sa.Integer(), server_default='30', nullable=False))
    with op.batch_alter_table('report_snapshots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('summary', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('report_snapshots', schema=None) as batch_op:
        batch_op.drop_column('summary')
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_column('history_days')
