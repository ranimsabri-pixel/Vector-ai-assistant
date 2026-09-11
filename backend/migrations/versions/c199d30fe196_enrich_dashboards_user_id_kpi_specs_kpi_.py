"""enrich dashboards: user_id, kpi_specs, kpi_results, generated_at, nullable html_content

Revision ID: c199d30fe196
Revises: 90bc62f1b92e
Create Date: 2026-06-25 13:02:06.690037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c199d30fe196'
down_revision: Union[str, None] = '90bc62f1b92e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ajouter user_id (NOT NULL — la table est vide, pas de risque)
    op.add_column(
        'dashboards',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        'dashboards_user_id_fkey',
        'dashboards',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_index('ix_dashboards_user_id', 'dashboards', ['user_id'])

    # 2. Rendre html_content et json_source nullable
    op.alter_column('dashboards', 'html_content',
                    existing_type=sa.Text(),
                    nullable=True)
    op.alter_column('dashboards', 'json_source',
                    existing_type=postgresql.JSONB(astext_type=sa.Text()),
                    nullable=True)

    # 3. Ajouter les nouveaux champs J14
    op.add_column(
        'dashboards',
        sa.Column('kpi_specs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'dashboards',
        sa.Column('kpi_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'dashboards',
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('dashboards', 'generated_at')
    op.drop_column('dashboards', 'kpi_results')
    op.drop_column('dashboards', 'kpi_specs')
    op.alter_column('dashboards', 'json_source',
                    existing_type=postgresql.JSONB(astext_type=sa.Text()),
                    nullable=False)
    op.alter_column('dashboards', 'html_content',
                    existing_type=sa.Text(),
                    nullable=False)
    op.drop_index('ix_dashboards_user_id', table_name='dashboards')
    op.drop_constraint('dashboards_user_id_fkey', 'dashboards', type_='foreignkey')
    op.drop_column('dashboards', 'user_id')