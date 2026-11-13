"""links that open one report without signing in

Revision ID: 0011_report_shares
Revises: 0010_chat_data_model
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0011_report_shares'
down_revision: Union[str, None] = '0010_chat_data_model'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'report_shares',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('report_id', sa.Integer(), sa.ForeignKey('reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('app_users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_viewed_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Every public request arrives as a token and nothing else, so that lookup has to be an index.
    op.create_index('ix_report_shares_token', 'report_shares', ['token'], unique=True)
    op.create_index('ix_report_shares_report_id', 'report_shares', ['report_id'])


def downgrade() -> None:
    op.drop_index('ix_report_shares_report_id', table_name='report_shares')
    op.drop_index('ix_report_shares_token', table_name='report_shares')
    op.drop_table('report_shares')
