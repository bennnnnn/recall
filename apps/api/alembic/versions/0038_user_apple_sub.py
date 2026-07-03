"""add apple_sub to users; google_sub nullable

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("apple_sub", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_apple_sub", "users", ["apple_sub"])
    op.alter_column("users", "google_sub", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "google_sub", existing_type=sa.String(), nullable=False)
    op.drop_constraint("uq_users_apple_sub", "users", type_="unique")
    op.drop_column("users", "apple_sub")
