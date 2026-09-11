"""fix type mismatches: quality_score Float, dataset_columns nullable

Revision ID: 47ddd719c056
Revises: fad808f243d8
Create Date: 2026-06-23 12:05:11.399218

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47ddd719c056'
down_revision: Union[str, None] = 'fad808f243d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cast quality_score INTEGER -> Float (préserve les valeurs existantes)
    op.alter_column(
        'datasets',
        'quality_score',
        existing_type=sa.INTEGER(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using='quality_score::double precision',
    )

    # Rendre nullables les colonnes de dataset_columns (alignées sur le modèle)
    op.alter_column('dataset_columns', 'dtype',
                    existing_type=sa.VARCHAR(length=50),
                    nullable=True)
    op.alter_column('dataset_columns', 'is_nullable',
                    existing_type=sa.BOOLEAN(),
                    nullable=True)
    op.alter_column('dataset_columns', 'is_date_main',
                    existing_type=sa.BOOLEAN(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('dataset_columns', 'is_date_main',
                    existing_type=sa.BOOLEAN(),
                    nullable=False)
    op.alter_column('dataset_columns', 'is_nullable',
                    existing_type=sa.BOOLEAN(),
                    nullable=False)
    op.alter_column('dataset_columns', 'dtype',
                    existing_type=sa.VARCHAR(length=50),
                    nullable=False)

    op.alter_column(
        'datasets',
        'quality_score',
        existing_type=sa.Float(),
        type_=sa.INTEGER(),
        existing_nullable=True,
        postgresql_using='quality_score::integer',
    )