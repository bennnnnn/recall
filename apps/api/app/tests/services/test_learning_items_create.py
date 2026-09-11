"""create_item must not block on pronunciation HTTP (quiz / turn-prep hot path)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.learning.items import create_item


@pytest.mark.asyncio
async def test_create_item_does_not_look_up_pronunciation():
    session = AsyncMock()
    created = MagicMock()

    with (
        patch(
            "app.services.learning.items.learning_items_repo.get_by_list_content",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.learning.items.learning_items_repo.create",
            new=AsyncMock(return_value=created),
        ) as create_mock,
    ):
        item = await create_item(
            session,
            user_id=uuid4(),
            project_id=uuid4(),
            content="apple",
        )

    assert item is created
    assert "pronunciation_url" not in create_mock.await_args.kwargs


@pytest.mark.asyncio
async def test_create_item_returns_existing_duplicate():
    session = AsyncMock()
    existing = MagicMock()
    with (
        patch(
            "app.services.learning.items.learning_items_repo.get_by_list_content",
            new=AsyncMock(return_value=existing),
        ),
        patch(
            "app.services.learning.items.learning_items_repo.create",
            new=AsyncMock(),
        ) as create_mock,
    ):
        item = await create_item(
            session,
            user_id=uuid4(),
            project_id=uuid4(),
            content="apple",
            list_title="Food",
        )
    assert item is existing
    create_mock.assert_not_awaited()
