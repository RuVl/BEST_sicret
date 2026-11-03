"""unique person telegram username

Ник в Telegram может принадлежать только одному Person (без учёта регистра).

Дубли появлялись, когда человек менял ник и не нажимал /start, а старый ник занимал другой.
Кому ник принадлежит сейчас, по БД не понять, поэтому upgrade обнуляет его у **всех** строк-дублей:
настоящий владелец вернёт его своим следующим /start. Downgrade убирает только индекс -
обнулённые ники не восстановить.

Revision ID: 1c7e4a9b3f20
Revises: b8d4e0f2a6c1
Create Date: 2026-11-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c7e4a9b3f20'
down_revision: Union[str, None] = 'b8d4e0f2a6c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        UPDATE persons SET telegram_username = NULL
        WHERE lower(telegram_username) IN (
            SELECT lower(telegram_username) FROM persons
            WHERE telegram_username IS NOT NULL
            GROUP BY lower(telegram_username)
            HAVING count(*) > 1
        )
        """
    )
    op.create_index(
        'uq_persons_telegram_username_lower',
        'persons',
        [sa.text('lower(telegram_username)')],
        unique=True,
        postgresql_where=sa.text('telegram_username IS NOT NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'uq_persons_telegram_username_lower',
        table_name='persons',
        postgresql_where=sa.text('telegram_username IS NOT NULL'),
    )
