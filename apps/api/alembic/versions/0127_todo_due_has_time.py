"""A to-do can have a date and no time.

Revision ID: 0127_todo_due_has_time
Revises: 0126_user_location_chosen_at

Picking a date on a to-do wrote a time with it (9:00, or the next hour), so a date alone
came with a time, a "Remind at" and a reminder. ``due_has_time`` false is a date alone:
``due_at`` holds the start of that day on the user's clock, no reminder goes out, and it
is overdue once the day has ended (``modules/todos/due_day.py``). Every existing row has
a time, so each starts true and keeps its reminders. A column with a server default: an
expand.

The open-duplicate unique (``uq_todo_open_content_due``, migration 0084) takes the flag
too: "Pay rent" on the 10th with no time is not the same to-do as "Pay rent" at 00:00
that day, and a date-only save that met the timed one came back as it, reminder and all.
It keeps its name, which the code reads to tell a duplicate from another failure. Adding
a column to it only lets more rows through, so every existing row satisfies it.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "0127_todo_due_has_time"
down_revision: Union[str, None] = "0126_user_location_chosen_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_UNIQUE = "uq_todo_open_content_due"
_OPEN_DATED = "WHERE checked = false AND due_at IS NOT NULL"


def upgrade() -> None:
    op.add_column(
        "todo_items",
        sa.Column("due_has_time", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # One transaction: the old unique holds until the new one replaces it.
    op.execute(f"DROP INDEX IF EXISTS {_UNIQUE}")
    op.execute(
        f"CREATE UNIQUE INDEX {_UNIQUE} "
        f"ON todo_items (user_id, lower(content), due_at, due_has_time) {_OPEN_DATED}"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_UNIQUE}")
    # A date alone and a same-titled time at its midnight would clash under the old unique:
    # the date alone moves a second on, as the timed rows before 0127 never did.
    op.execute(
        "UPDATE todo_items AS a SET due_at = a.due_at + interval '1 second' "
        "WHERE a.due_has_time = false AND a.checked = false AND EXISTS ("
        "SELECT 1 FROM todo_items AS b WHERE b.user_id = a.user_id "
        "AND lower(b.content) = lower(a.content) AND b.due_at = a.due_at "
        "AND b.due_has_time = true AND b.checked = false)"
    )
    op.execute(
        f"CREATE UNIQUE INDEX {_UNIQUE} ON todo_items (user_id, lower(content), due_at) "
        f"{_OPEN_DATED}"
    )
    op.drop_column("todo_items", "due_has_time")
