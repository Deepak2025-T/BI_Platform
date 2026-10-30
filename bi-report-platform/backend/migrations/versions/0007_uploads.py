"""uploads: logos and images people put on reports

Revision ID: 0007_uploads
Revises: 0006_template_category
Create Date: 2026-10-30 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007_uploads'
down_revision: Union[str, None] = '0006_template_category'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'uploads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stored_name', sa.String(length=80), nullable=False),
        sa.Column('original_name', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('content_type', sa.String(length=80), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['app_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_uploads_stored_name'), 'uploads', ['stored_name'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_uploads_stored_name'), table_name='uploads')
    op.drop_table('uploads')
