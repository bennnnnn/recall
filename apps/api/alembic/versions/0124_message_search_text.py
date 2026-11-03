"""Search reads a message's own words: what the user typed and what Recall replied.

Revision ID: 0124_message_search_text
Revises: 0123_list_and_retention_indexes

A user message stores the attachment lines after the words they typed: the
``[File: /attachments/…/file]`` and ``[Image: …]`` markers, then the file's extracted
text. A reply that shows a picture holds an ``[Image: …]`` line. The drawer's search
matched all of it: "attachments" found every message with a file, a 20-page PDF's text
matched ordinary words, and the excerpts showed ``[File: /attachments/27d4…/file]``.

``search_text`` is the message as a reader sees it, kept by Postgres from ``content``
(a stored generated column, so every writer is covered): a user message up to its first
attachment line, a reply without its ``[Image: …]`` lines. The trigram index moves to it.

The column add rewrites ``messages`` once; the indexes are built and dropped
CONCURRENTLY so writes keep flowing. The old index goes in the same release: the
previous release's search still runs without it, only slower, while the deploy rolls.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0124_message_search_text"
down_revision: Union[str, None] = "0123_list_and_retention_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy of app.models.orm.chat.MESSAGE_SEARCH_TEXT_SQL as of this revision.
_SEARCH_TEXT_SQL = r"""CASE WHEN role = 'user'
THEN regexp_replace(content, '(^|\n)\[(File|Image)[: (][\s\S]*$', '')
ELSE regexp_replace(content, '(^|\n)\[Image: /attachments/[^\n]*', '', 'g') END"""


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE messages ADD COLUMN IF NOT EXISTS search_text text "
        f"GENERATED ALWAYS AS ({_SEARCH_TEXT_SQL}) STORED"
    )
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_user_search_text_trgm "
            "ON messages USING gin (user_id, search_text gin_trgm_ops)"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_messages_user_content_trgm")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_messages_user_content_trgm "
            "ON messages USING gin (user_id, content gin_trgm_ops)"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_messages_user_search_text_trgm")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS search_text")
