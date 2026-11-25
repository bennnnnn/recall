"""The voice a reply is played in, apart from live talk's.

Revision ID: 0136_reply_voice
Revises: 0135_one_paid_plan

Settings → Voice has two pickers: live talk's voice (``tts_voice``) and the voice a reply
plays in when the user taps Listen (``reply_voice``), from the voices of the model that plays
replies in the app's language (``models/voice_catalog.py``). Null until the user picks one:
the reply voice then follows the live talk voice's gender.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0136_reply_voice"
down_revision: Union[str, None] = "0135_one_paid_plan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("reply_voice", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "reply_voice")
