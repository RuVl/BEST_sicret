"""add awg access and devices tables

Revision ID: c3e8f1a2b4d5
Revises: 9dc9c4a07413
Create Date: 2026-10-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e8f1a2b4d5'
down_revision: Union[str, None] = '9dc9c4a07413'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('awg_access',
    sa.Column('id', sa.Integer(), nullable=False, comment='Уникальный ID разрешения'),
    sa.Column('person_id', sa.Integer(), nullable=False, comment='Кому выдан доступ'),
    sa.Column('status', sa.String(length=16), server_default='granted', nullable=False, comment='granted/suspended/revoked'),
    sa.Column('device_limit', sa.Integer(), nullable=True, comment='Сколько устройств можно завести (NULL - лимит по умолчанию из настроек бота)'),
    sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Когда админ выдал доступ'),
    sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True, comment='Когда ключи выключены (выбыл из LBG или отозван админом)'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    comment='Доступ к AmneziaWG, выданный админом'
    )
    op.create_index(op.f('ix_awg_access_person_id'), 'awg_access', ['person_id'], unique=True)
    op.create_index(op.f('ix_awg_access_status'), 'awg_access', ['status'], unique=False)
    op.create_table('awg_devices',
    sa.Column('id', sa.Integer(), nullable=False, comment='Уникальный ID устройства'),
    sa.Column('access_id', sa.Integer(), nullable=False, comment='Разрешение, по которому заведено устройство'),
    sa.Column('number', sa.Integer(), nullable=False, comment='Номер устройства у человека (с 1)'),
    sa.Column('client_name', sa.String(length=15), nullable=False, comment='Имя клиента в AmneziaWG (lbg<person_id>-<number>)'),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True, comment='Когда конфиг последний раз отправлен человеку'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['access_id'], ['awg_access.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('access_id', 'number'),
    sa.UniqueConstraint('client_name'),
    comment='Устройство с ключом AmneziaWG'
    )
    op.create_index(op.f('ix_awg_devices_access_id'), 'awg_devices', ['access_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_awg_devices_access_id'), table_name='awg_devices')
    op.drop_table('awg_devices')
    op.drop_index(op.f('ix_awg_access_status'), table_name='awg_access')
    op.drop_index(op.f('ix_awg_access_person_id'), table_name='awg_access')
    op.drop_table('awg_access')
