"""drop_reports_table

Revision ID: a4a4f30141e9
Revises: 3fe755434ebe
Create Date: 2025-11-19 14:03:52.746652+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4a4f30141e9'
down_revision: Union[str, Sequence[str], None] = '3fe755434ebe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('reports')


def downgrade() -> None:
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('definition', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
