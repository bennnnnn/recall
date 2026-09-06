"""Add 'search' to attachments.source (reference-photo lookup)

Revision ID: 0081_attachment_source_search
Revises: 0080_retire_legacy_vocab

Distinguishes web-image-search lookups (real reference photos mirrored from
a search provider) from AI-generated images and user uploads, so the orphan
reaper and gallery filters can treat them distinctly from 'generated'.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0081_attachment_source_search"
down_revision: Union[str, None] = "0080_retire_legacy_vocab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_attachments_source", "attachments", type_="check")
    op.create_check_constraint(
        "ck_attachments_source",
        "attachments",
        "source IN ('upload', 'generated', 'search')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_attachments_source", "attachments", type_="check")
    op.create_check_constraint(
        "ck_attachments_source",
        "attachments",
        "source IN ('upload', 'generated')",
    )
