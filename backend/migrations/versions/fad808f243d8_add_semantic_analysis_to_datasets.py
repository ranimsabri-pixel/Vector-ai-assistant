"""add semantic_analysis to datasets

Revision ID: fad808f243d8
Revises: 1342b3938953
Create Date: 2026-06-23 10:04:08.732201

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fad808f243d8'
down_revision: Union[str, None] = '1342b3938953'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'datasets',
        sa.Column('semantic_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('datasets', 'semantic_analysis')