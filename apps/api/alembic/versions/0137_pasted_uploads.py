"""Whether an upload is text the user pasted into the composer.

Revision ID: 0137_pasted_uploads
Revises: 0136_reply_voice

The phone sends a long paste as a plain-text file. The server read it as the user's own
words when the file was named ``pasted-text.txt``, so a document anyone wrote and named so
was framed as words the user typed (security review, 2026-11-25). The composer's paste now
presigns with the purpose ``"paste"`` and the row keeps it here; nothing else makes an
upload a paste. Rows from before are documents.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0137_pasted_uploads"
down_revision: Union[str, None] = "0136_reply_voice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attachments",
        sa.Column("pasted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("attachments", "pasted")
