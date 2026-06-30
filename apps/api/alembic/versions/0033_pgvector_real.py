"""Real pgvector: vector column + HNSW index for semantic memory recall.

Replaces the prior app-side JSON-cosine approach with a real `vector(1536)`
column (matches openai/text-embedding-3-small) and an HNSW index for DB-side
cosine similarity ordering. The legacy `embedding_json` Text column is kept as
a fallback and for the backfill below.

On systems without the pgvector extension (e.g., CI test databases), the
vector features are skipped — the app falls back to in-memory JSON cosine.

Revision ID: 0033
Revises: 0032
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    bind = op.get_bind()

    # Try to create the pgvector extension. On systems where it isn't installed
    # (e.g., CI test DBs), skip the vector column + index — the app falls back
    # to in-memory JSON cosine when the DB-side search is unavailable.
    has_vector = False
    try:
        nested = bind.begin_nested()
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        nested.commit()
        has_vector = True
    except Exception:
        pass

    if not has_vector:
        return

    op.execute(f"ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})")

    # Backfill from legacy embedding_json, but only for rows whose stored vector
    # has the right dimensionality (mock/test rows use 8-dim vectors and would
    # fail the vector(1536) cast — those get re-embedded by the app on next turn).
    op.execute(
        f"""
        UPDATE memories
        SET embedding = embedding_json::vector({EMBEDDING_DIM})
        WHERE embedding IS NULL
          AND embedding_json IS NOT NULL
          AND array_length(
                string_to_array(replace(trim(both '[]' from embedding_json), ' ', ''), ','),
                1
              ) = {EMBEDDING_DIM}
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memories_embedding "
        "ON memories USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS embedding")
    # Intentionally do not drop the `vector` extension — it may be shared.
