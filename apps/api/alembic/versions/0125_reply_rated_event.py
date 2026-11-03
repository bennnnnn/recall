"""Allow the reply_rated product event.

Revision ID: 0125_reply_rated_event
Revises: 0124_message_search_text

A reply's thumbs up or down was saved on the message and read by nothing. The server now
records it as a metadata-only product event (the rating, the reply's model alias and its
kind: never its words), so answer quality can be read by model and kind. Widening the
check is an expand: the old release writes a subset of these names.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0125_reply_rated_event"
down_revision: Union[str, None] = "0124_message_search_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "ck_product_events_name"
_BEFORE = (
    "paywall_viewed",
    "purchase_started",
    "purchase_succeeded",
    "purchase_failed",
    "push_permission",
    "chat_ttft",
    "chat_turn_outcome",
)
_ADDED = ("reply_rated",)


def _check(names: tuple[str, ...]) -> str:
    return f"name IN {names!r}"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "product_events", type_="check")
    op.create_check_constraint(_CONSTRAINT, "product_events", _check(_BEFORE + _ADDED))


def downgrade() -> None:
    op.execute("DELETE FROM product_events WHERE name = 'reply_rated'")
    op.drop_constraint(_CONSTRAINT, "product_events", type_="check")
    op.create_check_constraint(_CONSTRAINT, "product_events", _check(_BEFORE))
