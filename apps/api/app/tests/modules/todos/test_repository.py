"""Tests for app.modules.todos.repository."""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _todo(todo_id, *, sort_order=None, topic="General"):
    item = MagicMock()
    item.id = todo_id
    item.sort_order = sort_order
    item.topic = topic
    return item


@pytest.fixture
def fake_session():
    return AsyncMock()
