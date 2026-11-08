"""When the user last set the Location switch: never chosen apart from turned off.

Revision ID: 0126_user_location_chosen_at
Revises: 0125_reply_rated_event

``users.location_enabled`` is a plain boolean that starts false, so a switch the user
turned off in Data controls and one never chosen looked the same. The phone either
turned a deliberate off back on at the next "near me" question, or, told to respect it,
never asked an account that had never chosen (a second account on the phone, an iOS
deny allowed later in Settings). ``location_chosen_at`` is stamped by the server each
time the switch is written; NULL is never chosen, and the account API reports that as
``location_enabled: null``. Existing rows start NULL: nothing recorded a choice, and a
switch that is on stays on. A nullable column, and ``location_enabled`` keeps its shape
for the release before this one: an expand.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "0126_user_location_chosen_at"
down_revision: Union[str, None] = "0125_reply_rated_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("location_chosen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "location_chosen_at")
