"""replace membership status with is_excluded

Revision ID: 9dc9c4a07413
Revises: a1c00b47f3ed
Create Date: 2026-08-05 13:49:56.195821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9dc9c4a07413'
down_revision: Union[str, None] = 'a1c00b47f3ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default нужен только на время заливки: в таблице уже есть строки.
    op.add_column(
        'lbg_members',
        sa.Column('is_excluded', sa.Boolean(), nullable=False, server_default=sa.false(),
                  comment='Исключён из группы (лист Ex-members)'),
    )
    op.execute("UPDATE lbg_members SET is_excluded = true WHERE membership_status = 'ex'")
    op.alter_column('lbg_members', 'is_excluded', server_default=None)

    op.alter_column('lbg_members', 'is_active',
               existing_type=sa.BOOLEAN(),
               comment='Может брать таски группы',
               existing_comment='Активный член',
               existing_nullable=False)
    op.drop_index(op.f('ix_lbg_members_membership_status'), table_name='lbg_members')
    op.create_index(op.f('ix_lbg_members_is_excluded'), 'lbg_members', ['is_excluded'], unique=False)
    op.drop_column('lbg_members', 'membership_status')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('lbg_members', sa.Column('membership_status', sa.VARCHAR(length=32), autoincrement=False, nullable=True, comment='Грубый статус: active/alumni/ex/inactive'))
    # Статус восстанавливаем грубо: разницу alumni/inactive флаги не хранят.
    op.execute(
        "UPDATE lbg_members SET membership_status = CASE "
        "WHEN is_excluded THEN 'ex' WHEN is_active THEN 'active' ELSE 'inactive' END"
    )
    op.drop_index(op.f('ix_lbg_members_is_excluded'), table_name='lbg_members')
    op.create_index(op.f('ix_lbg_members_membership_status'), 'lbg_members', ['membership_status'], unique=False)
    op.alter_column('lbg_members', 'is_active',
               existing_type=sa.BOOLEAN(),
               comment='Активный член',
               existing_comment='Может брать таски группы',
               existing_nullable=False)
    op.drop_column('lbg_members', 'is_excluded')
