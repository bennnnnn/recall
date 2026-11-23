"""Drop the retired JSON vector copies, users.response_style and the suggestions table.

Revision ID: 0133_drop_retired_columns
Revises: 0132_drop_german_italian_locales

No code reads or writes any of them: recall ranks the ``embedding`` vector in SQL (0118),
the account-wide reply length is gone and ``User`` stopped mapping ``response_style``
(0123), and the proactive suggestions were retired, so the data export and account delete
no longer read their rows. They waited in docs/ROLLBACK.md for the release after the one
that stopped reading them, but no release has shipped: the only Deploy run (2026-07-02)
failed, and production's database is created fresh on deploy day (PRODUCTION.md §0), so
there is no older image to roll back to.

The downgrade brings the columns back empty and nullable with their original types, and
the suggestions table back empty in its original shape; the dropped data is not restored.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0133_drop_retired_columns"
down_revision: Union[str, None] = "0132_drop_german_italian_locales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON_VECTOR_TABLES = ("memories", "message_chunks", "attachment_chunks")


def upgrade() -> None:
    # expand-contract: 0118 stopped reading embedding_json (rows since store NULL), 0123
    # stopped mapping users.response_style, and this release stops reading suggestions;
    # nothing has been deployed, so no running or rollback image reads any of them.
    for table in _JSON_VECTOR_TABLES:
        op.drop_column(table, "embedding_json")
    op.drop_column("users", "response_style")
    op.drop_index("ix_suggestions_user_id", table_name="suggestions")
    op.drop_table("suggestions")


def downgrade() -> None:
    op.create_table(
        "suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="suggestions_user_id_fkey", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), server_default="general", nullable=False),
        sa.Column("source", sa.String(50), server_default="model", nullable=False),
        sa.Column("dismissed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_suggestions_user_id", "suggestions", ["user_id"])
    op.add_column("users", sa.Column("response_style", sa.String(), nullable=True))
    for table in reversed(_JSON_VECTOR_TABLES):
        op.add_column(table, sa.Column("embedding_json", sa.Text(), nullable=True))
