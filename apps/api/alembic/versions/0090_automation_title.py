"""Add title column to automations.

Revision ID: 0090_automation_title
Revises: 0089_automations

Short human-readable title separate from the longer prompt body,
matching ChatGPT Tasks cards ("Remote SWE Job Watch").
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0090_automation_title"
down_revision: Union[str, None] = "0089_automations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "automations",
        sa.Column("title", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automations", "title")
