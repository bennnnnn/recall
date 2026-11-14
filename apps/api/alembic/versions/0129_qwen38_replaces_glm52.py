"""Point stored choices of GLM 5.2 at Qwen3.8 Flash.

Revision ID: 0129_qwen38_replaces_glm52
Revises: 0128_user_location_saved_at

The owner replaced GLM 5.2 with Qwen3.8 Flash (2026-11-11): cheaper, faster, and as right
on the maths it was measured on. A user who switched GLM 5.2 on in Settings, or picked it
for a chat, keeps a model in that place: ``glm-5.2`` becomes ``qwen-3.8-flash`` in
``users.enabled_models`` (in its position, once), ``users.default_model`` and
``chats.model``. ``messages.model`` is left alone: it records which model wrote each reply.
"""

import json
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "0129_qwen38_replaces_glm52"
down_revision: Union[str, None] = "0128_user_location_saved_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD = "glm-5.2"
NEW = "qwen-3.8-flash"


def replaced(models: list[str]) -> list[str]:
    """The switches with GLM 5.2 replaced in its place, each model once."""
    out: list[str] = []
    for model in models:
        model = NEW if model == OLD else model
        if model not in out:
            out.append(model)
    return out


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, enabled_models FROM users WHERE enabled_models::text LIKE :old"),
        {"old": f'%"{OLD}"%'},
    ).fetchall()
    for user_id, models in rows:
        if not isinstance(models, list):
            continue
        conn.execute(
            sa.text("UPDATE users SET enabled_models = CAST(:models AS jsonb) WHERE id = :id"),
            {"models": json.dumps(replaced(models)), "id": user_id},
        )
    conn.execute(
        sa.text("UPDATE users SET default_model = :new WHERE default_model = :old"),
        {"new": NEW, "old": OLD},
    )
    conn.execute(
        sa.text("UPDATE chats SET model = :new WHERE model = :old"), {"new": NEW, "old": OLD}
    )


def downgrade() -> None:
    # GLM 5.2 left the catalog: a stored choice of it could not be served.
    pass
