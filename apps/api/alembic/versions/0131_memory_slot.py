"""The one thing a single-valued memory fact sets.

Revision ID: 0131_memory_slot
Revises: 0130_new_account_defaults

A fact like "User lives in Paris" or "User is in 7th grade" answers one question about
the user; a newer answer replaces it. Nothing said which facts answer the same question,
so two homes, an age beside a contradicting school year, or a marriage beside another
stayed active together. Extraction now names the slot ("home", "school", "job") and a
write retires every other active fact in the same slot. Existing rows start NULL (no
slot) until the memory re-check reads them. A nullable column: an expand.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "0131_memory_slot"
down_revision: Union[str, None] = "0130_new_account_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("memories", sa.Column("slot", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("memories", "slot")
