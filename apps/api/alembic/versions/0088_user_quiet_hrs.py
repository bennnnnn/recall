"""Quiet hours columns on users.

Revision ID: 0088_user_quiet_hrs
Revises: 0087_memory_facts

Keep the revision id at or under 32 chars — ``alembic_version.version_num``
is ``varchar(32)`` (see 0063).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0088_user_quiet_hrs"
down_revision: Union[str, None] = "0087_memory_facts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "quiet_hours_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "quiet_hours_start_minute",
            sa.Integer(),
            nullable=False,
            server_default="1320",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "quiet_hours_end_minute",
            sa.Integer(),
            nullable=False,
            server_default="420",
        ),
    )
    op.create_check_constraint(
        "ck_users_quiet_hours_start",
        "users",
        "quiet_hours_start_minute >= 0 AND quiet_hours_start_minute <= 1439",
    )
    op.create_check_constraint(
        "ck_users_quiet_hours_end",
        "users",
        "quiet_hours_end_minute >= 0 AND quiet_hours_end_minute <= 1439",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_quiet_hours_end", "users", type_="check")
    op.drop_constraint("ck_users_quiet_hours_start", "users", type_="check")
    op.drop_column("users", "quiet_hours_end_minute")
    op.drop_column("users", "quiet_hours_start_minute")
    op.drop_column("users", "quiet_hours_enabled")
