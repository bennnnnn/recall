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

revision: str = "0138_todo_client_id"
down_revision: Union[str, None] = "0137_pasted_uploads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEX = "uq_todo_user_client_id"


def _index_valid(name: str) -> bool | None:
    """None when there is no such index; else whether Postgres may use it (0123's check)."""
    return (
        op.get_bind()
        .execute(
            sa.text("SELECT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:name)"),
            {"name": name},
        )
        .scalar()
    )


def upgrade() -> None:
    # Re-runnable: the concurrent build runs outside the migration's transaction, so a build that
    # fails (a lock wait past the deploy's timeout) leaves the column added and the revision not
    # stamped. The next deploy adds nothing twice and rebuilds an invalid index, which enforced
    # nothing (two rows under one id, and the id's lookup failing for good).
    with op.get_context().autocommit_block():
        op.execute("ALTER TABLE todo_items ADD COLUMN IF NOT EXISTS client_id UUID")
        if _index_valid(_INDEX) is False:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
        op.execute(
            f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX} "
            "ON todo_items (user_id, client_id) WHERE client_id IS NOT NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
        op.execute("ALTER TABLE todo_items DROP COLUMN IF EXISTS client_id")
