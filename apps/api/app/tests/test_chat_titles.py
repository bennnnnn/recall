"""Tests for chat title normalization."""

import pytest

from app.models.schemas import ChatOut
from app.services.chat_titles import normalize_chat_title


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("New chat", None),
        ("  new chat  ", None),
        ("Untitled", None),
        ("Chat", None),
        ("Valid topic name", "Valid topic name"),
        ('"Quoted title"', "Quoted title"),
        ("ab", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_chat_title(raw: str | None, expected: str | None):
    assert normalize_chat_title(raw) == expected


def test_chat_out_sanitizes_boring_title():
    from datetime import UTC, datetime
    from uuid import uuid4

    out = ChatOut(
        id=uuid4(),
        title="New chat",
        model="auto",
        pinned=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert out.title is None
