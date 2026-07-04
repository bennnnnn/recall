from types import SimpleNamespace
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
                summary=(
                    "Bini is a software developer who builds mobile apps "
                    "and backend services for Recall."
                ),
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
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=[0.1, 0.2, 0.3]),
        ),
    ):
        changed = await consolidate_user_memory_sections(session, Settings(), user_id=user_id)

    expected = "Bini is a software developer who builds mobile apps and backend services for Recall"
    assert changed is True
    upsert.assert_awaited_once()
    assert upsert.call_args.kwargs["items"][0][1] == expected


@pytest.mark.asyncio
async def test_consolidate_skips_suspiciously_short_rewrite():
    session = AsyncMock()
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    rewrite = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="profile",
                summary="Bini.",
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
    ):
        changed = await consolidate_user_memory_sections(session, Settings(), user_id=user_id)

    assert changed is False
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_consolidate_upserts_without_embedding_when_vector_missing():
    session = AsyncMock()
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    updated = SimpleNamespace(
        type="profile",
        text="Bini is a software developer with backend and mobile experience",
        embedding=None,
        embedding_json=None,
    )

    rewrite = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="profile",
                summary=updated.text,
                confidence=0.9,
            )
        ]
    )

    with (
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(side_effect=[[memory], [updated]]),
        ),
        patch(
            "app.background.memory_consolidation.litellm_gateway.rewrite_memory_sections",
            AsyncMock(return_value=rewrite),
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.upsert_sections",
            AsyncMock(),
        ),
        patch(
            "app.background.memory_consolidation.invalidate_memory_block",
            AsyncMock(),
        ),
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=None),
        ),
    ):
        changed = await consolidate_user_memory_sections(session, Settings(), user_id=user_id)

    assert changed is True
    assert updated.embedding is None


@pytest.mark.asyncio
async def test_consolidate_stores_embedding_when_vector_present():
    session = AsyncMock()
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    updated = SimpleNamespace(
        type="profile",
        text="Bini is a software developer with backend and mobile experience",
        embedding=None,
        embedding_json=None,
    )

    rewrite = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="profile",
                summary=updated.text,
                confidence=0.9,
            )
        ]
    )
    vector = [0.1, 0.2, 0.3]

    with (
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(side_effect=[[memory], [updated]]),
        ),
        patch(
            "app.background.memory_consolidation.litellm_gateway.rewrite_memory_sections",
            AsyncMock(return_value=rewrite),
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.upsert_sections",
            AsyncMock(),
        ),
        patch(
            "app.background.memory_consolidation.invalidate_memory_block",
            AsyncMock(),
        ),
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=vector),
        ),
        patch(
            "app.gateways.embedding_gateway.serialize_embedding",
            return_value="[0.1,0.2,0.3]",
        ),
    ):
        changed = await consolidate_user_memory_sections(session, Settings(), user_id=user_id)

    assert changed is True
    assert updated.embedding == vector
    assert updated.embedding_json == "[0.1,0.2,0.3]"
