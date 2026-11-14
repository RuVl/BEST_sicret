"""add awg device label

Revision ID: d4f9a3b2c6e7
Revises: c3e8f1a2b4d5
Create Date: 2026-10-20 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f9a3b2c6e7'
down_revision: Union[str, None] = 'c3e8f1a2b4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('awg_devices', sa.Column('label', sa.String(length=32), nullable=True, comment='Название устройства от владельца'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('awg_devices', 'label')
