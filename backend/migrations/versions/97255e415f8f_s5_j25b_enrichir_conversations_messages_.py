"""s5 j25b: enrichir conversations + messages pour persistance UI

Revision ID: 97255e415f8f
Revises: 0604f8766a70
Create Date: 2026-07-08 22:56:02.962431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '97255e415f8f'
down_revision: Union[str, None] = '0604f8766a70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # ---- Conversation.document_id (nullable, FK → documents avec SET NULL) ----
    op.add_column(
        "conversations",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_conversations_document_id"),
        "conversations",
        ["document_id"],
    )
    op.create_foreign_key(
        "fk_conversations_document_id_documents",
        "conversations",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ---- Message.message_kind (avec server_default pour rows existantes) ----
    op.add_column(
        "messages",
        sa.Column(
            "message_kind",
            sa.String(length=30),
            nullable=False,
            server_default="agent",
        ),
    )

    # ---- Message.tool_calls (JSONB nullable) ----
    op.add_column(
        "messages",
        sa.Column(
            "tool_calls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # ---- Message.sources (JSONB nullable) ----
    op.add_column(
        "messages",
        sa.Column(
            "sources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # ---- Message.extra_data (JSONB nullable) ----
    op.add_column(
        "messages",
        sa.Column(
            "extra_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Ordre inverse strict
    op.drop_column("messages", "extra_data")
    op.drop_column("messages", "sources")
    op.drop_column("messages", "tool_calls")
    op.drop_column("messages", "message_kind")
    op.drop_constraint(
        "fk_conversations_document_id_documents",
        "conversations",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_conversations_document_id"),
        table_name="conversations",
    )
    op.drop_column("conversations", "document_id")