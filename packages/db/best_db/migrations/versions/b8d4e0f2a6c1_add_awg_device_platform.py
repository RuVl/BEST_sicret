"""add awg device platform

Revision ID: b8d4e0f2a6c1
Revises: a7c3d9e5f1b4
Create Date: 2026-11-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d4e0f2a6c1'
down_revision: Union[str, None] = 'a7c3d9e5f1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('awg_devices', sa.Column('platform', sa.String(length=16), nullable=True, comment='android/ios/windows/macos/linux; NULL - не указана (заведено до выбора платформы)'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('awg_devices', 'platform')
