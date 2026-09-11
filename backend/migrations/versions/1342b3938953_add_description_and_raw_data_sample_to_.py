"""add description and raw_data_sample to datasets

Revision ID: 1342b3938953
Revises: 741e8c8966dd
Create Date: 2026-06-22 11:33:24.616915

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1342b3938953'
down_revision: Union[str, None] = '741e8c8966dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
   
    op.add_column('datasets', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('datasets', sa.Column('raw_data_sample', postgresql.JSONB(astext_type=sa.Text()), nullable=True))



def downgrade() -> None:
    op.drop_column('datasets', 'raw_data_sample')
    op.drop_column('datasets', 'description')