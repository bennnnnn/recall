"""A new account's settings: the owner's defaults (2026-11-11).

Revision ID: 0130_new_account_defaults
Revises: 0129_qwen38_replaces_glm52

Replies start professional with lots of emoji (``emoji_use`` "more"); sensitive memory,
email reminders and quiet hours (22:00-07:00, the start and end already stored) start on.
Only the column defaults change: an existing account keeps every setting it has.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0130_new_account_defaults"
down_revision: Union[str, None] = "0129_qwen38_replaces_glm52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW = {
    "response_tone": ("'professional'", "'casual'"),
    "emoji_use": ("'more'", "'some'"),
    "memory_include_sensitive": ("true", "false"),
    "email_reminders_enabled": ("true", "false"),
    "quiet_hours_enabled": ("true", "false"),
}


def upgrade() -> None:
    for column, (new, _old) in NEW.items():
        op.execute(f"ALTER TABLE users ALTER COLUMN {column} SET DEFAULT {new}")


def downgrade() -> None:
    for column, (_new, old) in NEW.items():
        op.execute(f"ALTER TABLE users ALTER COLUMN {column} SET DEFAULT {old}")
