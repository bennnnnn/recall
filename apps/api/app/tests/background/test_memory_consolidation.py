from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.background.memory_consolidation import consolidate_user_memory_sections
from app.core.config import Settings
from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult


@pytest.mark.asyncio
async def test_consolidate_skips_clean_sections():
    session = AsyncMock()
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "Bini is a software engineer at Hooh."

    with patch(
        "app.background.memory_consolidation.memories_repo.list_for_user",
        AsyncMock(return_value=[memory]),
    ):
        changed = await consolidate_user_memory_sections(session, Settings(), user_id=user_id)

    assert changed is False


@pytest.mark.asyncio
async def test_consolidate_rewrites_messy_sections():
    session = AsyncMock()
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    rewrite = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="profile",
                summary="Bini is a software developer.",
                confidence=0.9,
            )
        ]
    )

    with (
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(return_value=[memory]),
        ),
        patch(
            "app.background.memory_consolidation.litellm_gateway.rewrite_memory_sections",
            AsyncMock(return_value=rewrite),
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.upsert_sections",
            AsyncMock(),
        ) as upsert,
        patch(
            "app.background.memory_consolidation.invalidate_memory_block",
            AsyncMock(),
        ),
    ):
        changed = await consolidate_user_memory_sections(session, Settings(), user_id=user_id)

    assert changed is True
    upsert.assert_awaited_once()
    assert upsert.call_args.kwargs["items"][0][1] == "Bini is a software developer"
