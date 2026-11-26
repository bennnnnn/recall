"""The embedding width: every pgvector column, the mock vector and each length check.

Migrations wrote the columns at this width (memories, attachment and message chunks); a
vector of any other length is stored as none and never searched with.
"""

EMBEDDING_DIM = 1536


def stored_vector(vector: list[float] | None) -> list[float] | None:
    """``vector`` when a column can hold it, else None (the row is kept unembedded)."""
    return vector if vector is not None and len(vector) == EMBEDDING_DIM else None
