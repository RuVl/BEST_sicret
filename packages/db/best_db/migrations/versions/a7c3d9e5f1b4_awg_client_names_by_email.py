"""awg client names by email

Revision ID: a7c3d9e5f1b4
Revises: f6b2c8d4e0a3
Create Date: 2026-11-02 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3d9e5f1b4'
down_revision: Union[str, None] = 'f6b2c8d4e0a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('awg_devices', 'client_name',
               existing_type=sa.String(length=32),
               type_=sa.String(length=128),
               comment='Email клиента AmneziaWG в 3x-ui (awg-<number>-<email человека>)',
               existing_comment='Email клиента AmneziaWG в 3x-ui (awg-lbg<person_id>-<number>)',
               existing_nullable=False)
    # Существующие имена не трогаем: под ними в панели уже могут быть выданные ключи, и смена
    # имени только в БД оставила бы их без учёта. Бот сам переименует устройство, когда будет
    # заводить ему клиента в панели (``ensure_peer``).


def downgrade() -> None:
    """Downgrade schema."""
    # Откат не пройдёт, пока есть имена длиннее 32 символов: укоротить их без потери ключей нельзя.
    op.alter_column('awg_devices', 'client_name',
               existing_type=sa.String(length=128),
               type_=sa.String(length=32),
               comment='Email клиента AmneziaWG в 3x-ui (awg-lbg<person_id>-<number>)',
               existing_comment='Email клиента AmneziaWG в 3x-ui (awg-<number>-<email человека>)',
               existing_nullable=False)
