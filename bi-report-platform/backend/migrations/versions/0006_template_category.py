"""templates: the domain a template belongs to (ERP, GRC, Common, Uncategorised)

Revision ID: 0006_template_category
Revises: 0005_report_history
Create Date: 2026-10-30 16:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006_template_category'
down_revision: Union[str, None] = '0005_report_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=40),
                                      server_default='Uncategorised', nullable=False))
    # The built-in GRC dashboards are the only ones whose domain can be told from the name here;
    # the rest are set when the API starts and re-reads its built-in templates.
    op.execute("UPDATE report_templates SET category = 'GRC' WHERE name LIKE 'OpenPages:%'")


def downgrade() -> None:
    with op.batch_alter_table('report_templates', schema=None) as batch_op:
        batch_op.drop_column('category')
