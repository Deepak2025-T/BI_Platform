"""saved chart colour palettes

Revision ID: 0009_color_palettes
Revises: 0008_template_module
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0009_color_palettes'
down_revision: Union[str, None] = '0008_template_module'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'color_palettes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=60), nullable=False),
        sa.Column('colors', sa.JSON(), nullable=False),
        sa.Column('owner_id', sa.Integer(), sa.ForeignKey('app_users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # The page lists a person's own palettes and the shared ones together, in name order.
    op.create_index('ix_color_palettes_owner', 'color_palettes', ['owner_id', 'name'])


def downgrade() -> None:
    op.drop_index('ix_color_palettes_owner', table_name='color_palettes')
    op.drop_table('color_palettes')
