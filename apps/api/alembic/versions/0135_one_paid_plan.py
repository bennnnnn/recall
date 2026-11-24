"""One paid plan: Plus is gone, Pro is the only paid plan.

Revision ID: 0135_one_paid_plan
Revises: 0134_drop_retired_columns

Plans are now free and pro. Pro is billed monthly or yearly; both store products grant
the same RevenueCat entitlement, so the period never reaches the database. No one ever
paid for Plus (only dev accounts were on it), so a Plus row moves up to Pro rather than
down to Free.

The downgrade restores the three-plan constraint; the rows moved to Pro stay on Pro.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0135_one_paid_plan"
down_revision: Union[str, None] = "0134_drop_retired_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET plan = 'pro' WHERE plan = 'plus'")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_plan")
    op.create_check_constraint("ck_users_plan", "users", "plan IN ('free', 'pro')")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_plan")
    op.create_check_constraint("ck_users_plan", "users", "plan IN ('free', 'plus', 'pro')")
