"""TodoCreate / TodoUpdate field bounds (create/reorder parity)."""

import pytest
from pydantic import ValidationError

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
