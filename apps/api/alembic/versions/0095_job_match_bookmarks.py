"""Separate job bookmarks from application stages.

Revision ID: 0095_job_match_bookmarks
Revises: 0094_job_match_scan_fields
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0095_job_match_bookmarks"
down_revision: Union[str, None] = "0094_job_match_scan_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_STATUSES = "('new', 'saved', 'applied', 'interviewing', 'offer', 'rejected', 'hidden')"
_NEW_STATUSES = "('new', 'applied', 'interviewing', 'offer', 'rejected', 'hidden')"


def upgrade() -> None:
    op.add_column(
        "job_matches",
        sa.Column("is_saved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE job_matches SET is_saved = true, status = 'new' WHERE status = 'saved'")
    op.drop_constraint("ck_job_matches_status", "job_matches", type_="check")
    op.create_check_constraint(
        "ck_job_matches_status",
        "job_matches",
        f"status IN {_NEW_STATUSES}",
    )
    op.alter_column("job_matches", "is_saved", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_job_matches_status", "job_matches", type_="check")
    op.create_check_constraint(
        "ck_job_matches_status",
        "job_matches",
        f"status IN {_OLD_STATUSES}",
    )
    op.execute("UPDATE job_matches SET status = 'saved' WHERE is_saved = true AND status = 'new'")
    op.drop_column("job_matches", "is_saved")
