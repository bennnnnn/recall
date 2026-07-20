"""Tests for chat title normalization."""

import pytest

from app.models.schemas import ChatOut
from app.services.chat_titles import normalize_chat_title, sanitize_manual_chat_title


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("New chat", None),
        ("  new chat  ", None),
        ("Untitled", None),
        ("Chat", None),
        ("Valid topic name", "Valid topic name"),
        ('"Quoted title"', "Quoted title"),
        ('"My Trip Plan".', "My Trip Plan"),
        ('"My Trip Plan"!', "My Trip Plan"),
        ("\u201cMy Trip Plan\u201d.", "My Trip Plan"),
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


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('  "Pinned note"  ', "Pinned note"),
        ('"My Trip Plan".', "My Trip Plan"),
        ("New chat", "New chat"),
        ("ab", "ab"),
        ("", None),
        ("x" * 81, None),
    ],
)
def test_sanitize_manual_chat_title(raw: str, expected: str | None):
    assert sanitize_manual_chat_title(raw) == expected


def test_search_result_sanitizes_chat_title():
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.models.schemas import SearchResultItem

    item = SearchResultItem(
        chat_id=uuid4(),
        chat_title='"My Trip Plan".',
        content="hi",
        role="user",
        created_at=datetime.now(UTC),
    )
    assert item.chat_title == "My Trip Plan"
