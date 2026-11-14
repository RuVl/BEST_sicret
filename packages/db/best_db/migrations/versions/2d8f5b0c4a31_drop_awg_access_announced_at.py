"""drop awg access announced_at

Рассылка ``awg-announce`` заменена общей ``make broadcast``, отметка «кому уже ушло» больше не нужна.
Downgrade возвращает пустую колонку: прежние отметки не восстановить.

Revision ID: 2d8f5b0c4a31
Revises: 1c7e4a9b3f20
Create Date: 2026-11-03 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d8f5b0c4a31'
down_revision: Union[str, None] = '1c7e4a9b3f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('awg_access', 'announced_at')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('awg_access', sa.Column('announced_at', sa.DateTime(timezone=True), nullable=True, comment='Когда человеку ушла рассылка о переезде AmneziaWG (повторно не шлём)'))
