"""A name saved all in lowercase gets a capital at the start of each part.

Revision ID: 0133_proper_case_names
Revises: 0132_drop_german_italian_locales

The name went into every prompt as typed, and replies greeted and signed "bini" (owner,
2026-11-07, again 2026-11-22). New writes go through ``core.validation.proper_name``; this
does the same to the rows saved before. Only a name with no capital in it changes ("McDonald"
and "de Silva" stay), and a script with no case is equal to its upper case, so it is left
alone. Only a name of plain ASCII changes here: Postgres's initcap reads an accent typed as
its own mark as a word break ("pe\u0301rez" to "PéRez"), so any other name keeps as saved until
its next edit, which ``proper_name`` reads letter by letter (review, #2538). Data only; the
downgrade cannot know who typed which, so it leaves the rows as they are.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0133_proper_case_names"
down_revision: Union[str, None] = "0132_drop_german_italian_locales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET name = initcap(name) "
        "WHERE name IS NOT NULL AND name = lower(name) AND name <> upper(name) "
        "AND octet_length(name) = char_length(name)"
    )


def downgrade() -> None:
    pass
