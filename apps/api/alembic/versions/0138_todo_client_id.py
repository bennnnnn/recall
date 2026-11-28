"""A to-do's client id: the phone's name for one create, so a retry adds nothing.

Revision ID: 0138_todo_client_id
Revises: 0137_pasted_uploads

The To-do screen's Save sent no id of its own: a create whose answer was lost (a dropped
connection, a timeout) and Save tapped again made a second to-do (pre-launch review,
2026-11-27). The phone now names each create with an id it makes, kept across its retries,
and the server answers a create it already holds under that id with the row it made. The
id is unique per account; rows from before, and a chat card's adds, have none.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0138_todo_client_id"
down_revision: Union[str, None] = "0137_pasted_uploads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "todo_items",
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Built beside the writes, as 0117's: the table keeps taking to-dos meanwhile.
    with op.get_context().autocommit_block():
        op.create_index(
            "uq_todo_user_client_id",
            "todo_items",
            ["user_id", "client_id"],
            unique=True,
            postgresql_where=sa.text("client_id IS NOT NULL"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "uq_todo_user_client_id",
            table_name="todo_items",
            postgresql_concurrently=True,
            if_exists=True,
        )
    op.drop_column("todo_items", "client_id")
