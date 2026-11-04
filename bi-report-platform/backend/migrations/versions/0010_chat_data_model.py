"""the OpenPages data model a chat is held to

Revision ID: 0010_chat_data_model
Revises: 0009_color_palettes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0010_chat_data_model'
down_revision: Union[str, None] = '0009_color_palettes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Empty means every object type shared from the connection, which is what every chat up to now
    # has been doing, so existing chats carry on unchanged.
    op.add_column('chat_conversations',
                  sa.Column('data_model', sa.String(length=120), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('chat_conversations', 'data_model')
