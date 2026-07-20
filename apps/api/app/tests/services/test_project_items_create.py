"""create_item must not block on pronunciation HTTP (quiz / turn-prep hot path)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.projects.items import create_item


@pytest.mark.asyncio
async def test_create_item_skips_pronunciation_lookup():
    session = AsyncMock()
    created = MagicMock()
    created.pronunciation_url = None

    with (
        patch(
            "app.services.projects.items.project_items_repo.create",
            new=AsyncMock(return_value=created),
        ) as create_mock,
        patch(
            "app.gateways.pronunciation_lookup.lookup_pronunciation_url",
            new=AsyncMock(return_value="https://example.com/a.mp3"),
        ) as lookup_mock,
    ):
        item = await create_item(
            session,
            user_id=uuid4(),
            project_id=uuid4(),
            content="apple",
        )

    assert item is created
    lookup_mock.assert_not_awaited()
    assert create_mock.await_args.kwargs["pronunciation_url"] is None
