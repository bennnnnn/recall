"""Schema field bounds (create/reorder / chat request hygiene)."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.schemas.chats import ChatMessageRequest
from app.models.schemas.todos import TodoUpdate


def test_todo_update_rejects_oversized_content():
    with pytest.raises(ValidationError):
        TodoUpdate(content="x" * 1001)


def test_todo_update_rejects_negative_sort_order():
    with pytest.raises(ValidationError):
        TodoUpdate(sort_order=-1)


def test_todo_update_accepts_bounded_fields():
    body = TodoUpdate(content="ok", sort_order=0)
    assert body.content == "ok"
    assert body.sort_order == 0


def test_chat_message_rejects_too_many_attachment_ids():
    with pytest.raises(ValidationError):
        ChatMessageRequest(content="hi", attachment_ids=[uuid4() for _ in range(11)])
