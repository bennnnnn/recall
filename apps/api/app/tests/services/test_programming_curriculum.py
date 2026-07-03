from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.programming_curriculum import seed_programming_curriculum


def _curriculum_item_count() -> int:
    from app.services.programming_curriculum import PROGRAMMING_CURRICULUM

    return sum(len(topics) for _, topics in PROGRAMMING_CURRICULUM)


@pytest.mark.asyncio
async def test_seed_programming_curriculum_creates_on_empty():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()

    session.add = MagicMock()
    session.commit = AsyncMock()

    with patch(
        "app.services.programming_curriculum.project_items_repo.list_for_user",
        AsyncMock(return_value=[]),
    ):
        created = await seed_programming_curriculum(
            session,
            user_id=user_id,
            project_id=project_id,
        )

    assert created == _curriculum_item_count()
    assert session.add.call_count == _curriculum_item_count()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_seed_programming_curriculum_idempotent():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()

    session.add = MagicMock()
    session.commit = AsyncMock()

    with patch(
        "app.services.programming_curriculum.project_items_repo.list_for_user",
        AsyncMock(return_value=[MagicMock()]),
    ):
        created = await seed_programming_curriculum(
            session,
            user_id=user_id,
            project_id=project_id,
        )

    assert created == 0
    session.add.assert_not_called()
    session.commit.assert_not_called()
