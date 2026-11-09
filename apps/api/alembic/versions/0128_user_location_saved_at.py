"""When the phone last saved the user's place.

Revision ID: 0128_user_location_saved_at
Revises: 0127_todo_due_has_time

A turn that brings no fix of its own reads ``users.location``, the place the phone last
saved. Nothing said when that was: a place saved in San Francisco in the morning answered
"What's the weather tomorrow?" in New York that evening as if it were current. The server
stamps ``location_saved_at`` each time the phone sends the place (the same one again
included); a turn trusts the saved place only while it is recent. Existing rows start NULL,
an age no turn trusts, until the phone next saves its place. A nullable column: an expand.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "0128_user_location_saved_at"
down_revision: Union[str, None] = "0127_todo_due_has_time"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("location_saved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "location_saved_at")
