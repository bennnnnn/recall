"""A to-do can have a date and no time.

Revision ID: 0127_todo_due_has_time
Revises: 0126_user_location_chosen_at

Picking a date on a to-do wrote a time with it (9:00, or the next hour), so a date alone
came with a time, a "Remind at" and a reminder. ``due_has_time`` false is a date alone:
``due_at`` holds the start of that day on the user's clock, no reminder goes out, and it
is overdue once the day has ended (``modules/todos/due_day.py``). Every existing row has
a time, so each starts true and keeps its reminders. A column with a server default: an
expand.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "0127_todo_due_has_time"
down_revision: Union[str, None] = "0126_user_location_chosen_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "todo_items",
        sa.Column("due_has_time", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("todo_items", "due_has_time")
