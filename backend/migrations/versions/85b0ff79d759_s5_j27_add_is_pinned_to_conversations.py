"""s5 j27: add is_pinned to conversations

Revision ID: 85b0ff79d759
Revises: 97255e415f8f
Create Date: 2026-07-10 22:43:05.293480

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85b0ff79d759'
down_revision: Union[str, None] = '97255e415f8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
        op.drop_column("conversations", "is_pinned")

