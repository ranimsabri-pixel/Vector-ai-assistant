"""add auto_kpis JSONB to datasets

Revision ID: 90bc62f1b92e
Revises: 47ddd719c056
Create Date: 2026-06-24 13:12:16.660017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '90bc62f1b92e'
down_revision: Union[str, None] = '47ddd719c056'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'datasets',
        sa.Column('auto_kpis', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('datasets', 'auto_kpis')