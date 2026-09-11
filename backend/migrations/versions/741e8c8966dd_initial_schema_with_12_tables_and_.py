"""initial schema with 12 tables and pgvector

Revision ID: 741e8c8966dd
Revises: 
Create Date: 2026-06-19 10:36:53.572803

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '741e8c8966dd'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    """Upgrade schema."""
    # Active l'extension pgvector AVANT de créer les tables (chunks.embedding en dépend)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('agents',
    sa.Column('slug', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('role', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('system_prompt', sa.Text(), nullable=False),
    sa.Column('accent_color', sa.String(length=7), nullable=False),
    sa.Column('avatar_url', sa.String(length=500), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agents_slug'), 'agents', ['slug'], unique=True)
    op.create_table('users',
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('conversations',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('agent_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_user_id'), 'conversations', ['user_id'], unique=False)
    op.create_table('datasets',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=True),
    sa.Column('column_count', sa.Integer(), nullable=True),
    sa.Column('quality_score', sa.Integer(), nullable=True),
    sa.Column('quality_issues', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_datasets_user_id'), 'datasets', ['user_id'], unique=False)
    op.create_table('documents',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('chunk_count', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_user_id'), 'documents', ['user_id'], unique=False)
    op.create_table('analyses',
    sa.Column('dataset_id', sa.UUID(), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_analyses_dataset_id'), 'analyses', ['dataset_id'], unique=False)
    op.create_table('chunks',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('token_count', sa.Integer(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chunks_document_id'), 'chunks', ['document_id'], unique=False)
    op.create_table('dashboards',
    sa.Column('dataset_id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('html_content', sa.Text(), nullable=False),
    sa.Column('json_source', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dashboards_dataset_id'), 'dashboards', ['dataset_id'], unique=False)
    op.create_table('dataset_columns',
    sa.Column('dataset_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('dtype', sa.String(length=50), nullable=False),
    sa.Column('is_nullable', sa.Boolean(), nullable=False),
    sa.Column('unique_count', sa.Integer(), nullable=True),
    sa.Column('null_count', sa.Integer(), nullable=True),
    sa.Column('sample_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('is_date_main', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dataset_columns_dataset_id'), 'dataset_columns', ['dataset_id'], unique=False)
    op.create_table('kpis',
    sa.Column('dataset_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('formula', sa.Text(), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('target_value', sa.Float(), nullable=True),
    sa.Column('display_format', sa.String(length=50), nullable=False),
    sa.Column('display_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_kpis_dataset_id'), 'kpis', ['dataset_id'], unique=False)
    op.create_table('messages',
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)
    op.create_table('kpi_values',
    sa.Column('kpi_id', sa.UUID(), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['kpi_id'], ['kpis.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_kpi_values_computed_at'), 'kpi_values', ['computed_at'], unique=False)
    op.create_index(op.f('ix_kpi_values_kpi_id'), 'kpi_values', ['kpi_id'], unique=False)
    # ### end Alembic commands ###
    # Index IVFFlat pour la recherche par similarité cosinus
    op.execute(
        "CREATE INDEX ix_chunks_embedding_cosine "
        "ON chunks USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_kpi_values_kpi_id'), table_name='kpi_values')
    op.drop_index(op.f('ix_kpi_values_computed_at'), table_name='kpi_values')
    op.drop_table('kpi_values')
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_kpis_dataset_id'), table_name='kpis')
    op.drop_table('kpis')
    op.drop_index(op.f('ix_dataset_columns_dataset_id'), table_name='dataset_columns')
    op.drop_table('dataset_columns')
    op.drop_index(op.f('ix_dashboards_dataset_id'), table_name='dashboards')
    op.drop_table('dashboards')
    op.drop_index(op.f('ix_chunks_document_id'), table_name='chunks')
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_cosine")
    op.drop_table('chunks')
    op.drop_index(op.f('ix_analyses_dataset_id'), table_name='analyses')
    op.drop_table('analyses')
    op.drop_index(op.f('ix_documents_user_id'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_datasets_user_id'), table_name='datasets')
    op.drop_table('datasets')
    op.drop_index(op.f('ix_conversations_user_id'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_agents_slug'), table_name='agents')
    op.drop_table('agents')
    # ### end Alembic commands ###

    # Supprime l'extension pgvector EN DERNIER (après avoir supprimé toutes les tables)
    op.execute("DROP EXTENSION IF EXISTS vector")
