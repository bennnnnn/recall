"""Add domain on vocab decks and refresh the catalog tree.

Revision ID: 0072_vocab_domain_tree
Revises: 0071_drop_trivia_projects
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0072_vocab_domain_tree"
down_revision: Union[str, None] = "0071_drop_trivia_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vocab_decks",
        sa.Column("domain", sa.String(200), nullable=False, server_default=""),
    )
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE project_items SET catalog_entry_id = NULL"))
    conn.execute(sa.text("DELETE FROM vocab_entries"))
    conn.execute(sa.text("DELETE FROM vocab_decks"))

    from app.content.vocab_catalog import all_catalog_decks, word_id

    decks_table = sa.table(
        "vocab_decks",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("target_language", sa.String),
        sa.column("slug", sa.String),
        sa.column("title", sa.String),
        sa.column("domain", sa.String),
        sa.column("kind", sa.String),
        sa.column("sort_order", sa.Integer),
    )
    entries_table = sa.table(
        "vocab_entries",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("deck_id", postgresql.UUID(as_uuid=True)),
        sa.column("content", sa.Text),
        sa.column("definition", sa.Text),
        sa.column("example_sentence", sa.Text),
        sa.column("sort_order", sa.Integer),
    )
    decks = all_catalog_decks()
    op.bulk_insert(
        decks_table,
        [
            {
                "id": deck.id,
                "target_language": deck.language,
                "slug": deck.slug,
                "title": deck.title,
                "domain": deck.domain,
                "kind": deck.kind,
                "sort_order": deck.sort_order,
            }
            for deck in decks
        ],
    )
    op.bulk_insert(
        entries_table,
        [
            {
                "id": word_id(deck, word),
                "deck_id": deck.id,
                "content": word.content,
                "definition": word.definition,
                "example_sentence": word.example_sentence,
                "sort_order": index,
            }
            for deck in decks
            for index, word in enumerate(deck.words)
        ],
    )


def downgrade() -> None:
    op.drop_column("vocab_decks", "domain")
