"""prefix awg client names

Revision ID: f6b2c8d4e0a3
Revises: e5a1b7c3d9f2
Create Date: 2026-11-01 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b2c8d4e0a3'
down_revision: Union[str, None] = 'e5a1b7c3d9f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('awg_devices', 'client_name',
               existing_type=sa.String(length=15),
               type_=sa.String(length=32),
               comment='Email клиента AmneziaWG в 3x-ui (awg-lbg<person_id>-<number>)',
               existing_comment='Имя клиента в AmneziaWG (lbg<person_id>-<number>)',
               existing_nullable=False)
    # Устройства со старого сервера: в 3x-ui их клиентов ещё нет - бот заведёт их под новым именем.
    op.execute("UPDATE awg_devices SET client_name = 'awg-' || client_name WHERE client_name NOT LIKE 'awg-%'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE awg_devices SET client_name = substr(client_name, 5) WHERE client_name LIKE 'awg-%'")
    op.alter_column('awg_devices', 'client_name',
               existing_type=sa.String(length=32),
               type_=sa.String(length=15),
               comment='Имя клиента в AmneziaWG (lbg<person_id>-<number>)',
               existing_comment='Email клиента AmneziaWG в 3x-ui (awg-lbg<person_id>-<number>)',
               existing_nullable=False)
