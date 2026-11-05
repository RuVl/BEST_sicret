"""add awg access announced_at

Revision ID: e5a1b7c3d9f2
Revises: d4f9a3b2c6e7
Create Date: 2026-11-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a1b7c3d9f2'
down_revision: Union[str, None] = 'd4f9a3b2c6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('awg_access', sa.Column('announced_at', sa.DateTime(timezone=True), nullable=True, comment='Когда человеку ушла рассылка о переезде AmneziaWG (повторно не шлём)'))
    op.create_table_comment('awg_access', 'Доступ мембера к AmneziaWG', existing_comment='Доступ к AmneziaWG, выданный админом')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table_comment('awg_access', 'Доступ к AmneziaWG, выданный админом', existing_comment='Доступ мембера к AmneziaWG')
    op.drop_column('awg_access', 'announced_at')
