"""German and Italian are no longer app languages: their accounts move to English.

Revision ID: 0132_drop_german_italian_locales
Revises: 0131_memory_slot

The app now offers Hindi in their place (owner, 2026-11-20). A saved ``de`` or ``it``
locale (with or without a region, "de-AT") would be refused by the profile check and
name a language the phone no longer has, so those users are set to English, which they
can change in Settings. Data only; the downgrade cannot know who chose which, so it
leaves the rows as they are.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0132_drop_german_italian_locales"
down_revision: Union[str, None] = "0131_memory_slot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET locale = 'en' WHERE lower(split_part(locale, '-', 1)) IN ('de', 'it')"
    )


def downgrade() -> None:
    pass
