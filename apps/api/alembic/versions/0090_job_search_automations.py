"""Add dedicated My Job search metadata to automations.

Revision ID: 0090_job_search
Revises: 0089_automations
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0090_job_search"
down_revision: Union[str, None] = "0089_automations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "automations",
        sa.Column("kind", sa.String(length=24), nullable=False, server_default="generic"),
    )
    op.add_column("automations", sa.Column("config_json", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_automations_kind",
        "automations",
        "kind IN ('generic', 'job_search')",
    )
    # My Job is one durable search profile per user. Generic automations remain
    # available to legacy clients for inspection/deletion, but the product no
    # longer exposes them. Pause existing active rows so an invisible retired
    # task cannot keep running after users upgrade to the job-search-only UI.
    op.execute(
        sa.text(
            "UPDATE automations SET status = 'paused' WHERE kind = 'generic' AND status = 'active'"
        )
    )
    op.create_index(
        "uq_automations_job_search_user",
        "automations",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'job_search'"),
    )


def downgrade() -> None:
    op.drop_index("uq_automations_job_search_user", table_name="automations")
    op.drop_constraint("ck_automations_kind", "automations", type_="check")
    op.drop_column("automations", "config_json")
    op.drop_column("automations", "kind")
