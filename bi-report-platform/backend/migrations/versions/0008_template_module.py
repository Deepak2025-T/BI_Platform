"""template module (sub-category within a category, e.g. GRC > ORM)

Revision ID: 0008_template_module
Revises: 0007_uploads
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0008_template_module'
down_revision: Union[str, None] = '0007_uploads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('report_templates',
                  sa.Column('module', sa.String(length=40), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('report_templates', 'module')
