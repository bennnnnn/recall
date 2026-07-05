from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.background.memory_consolidation import consolidate_user_memory_sections
from app.core.config import Settings
from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult


class _FakeSessionCM:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _consolidation_sessions(*, count: int = 1) -> tuple[AsyncMock, list[_FakeSessionCM]]:
    session = AsyncMock()
    session.commit = AsyncMock()
    return session, [_FakeSessionCM(session) for _ in range(count)]


@pytest.mark.asyncio
async def test_consolidate_skips_clean_sections():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "Bini is a software engineer at Hooh."

    _, session_locals = _consolidation_sessions()
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(return_value=[memory]),
        ),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is False


@pytest.mark.asyncio
async def test_consolidate_rewrites_messy_sections():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    rewrite = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="profile",
                summary=(
                    "Bini (Binalfew) is a software developer who builds mobile apps "
                    "and backend services for Recall."
                ),
                confidence=0.9,
            )
        ]
    )

    _, session_locals = _consolidation_sessions(count=2)
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
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
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    expected = (
        "Bini (Binalfew) is a software developer who builds mobile apps "
        "and backend services for Recall"
    )
    assert changed is True
    upsert.assert_awaited_once()
    assert upsert.call_args.kwargs["items"][0][1] == expected


@pytest.mark.asyncio
async def test_consolidate_skips_suspiciously_short_rewrite():
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

    _, session_locals = _consolidation_sessions()
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
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
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is False
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_consolidate_skips_when_model_omits_existing_section():
    user_id = uuid4()
    profile = AsyncMock()
    profile.type = "profile"
    profile.text = "User's name is Bini. User's name is Binalfew. User is a developer."
    preference = AsyncMock()
    preference.type = "preference"
    preference.text = "Prefers concise answers. Prefers concise answers. Prefers concise answers."

    rewrite = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="profile",
                summary=(
                    "Bini (Binalfew) is a software developer who builds mobile apps "
                    "and backend services for Recall."
                ),
                confidence=0.9,
            )
        ]
    )

    _, session_locals = _consolidation_sessions()
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(return_value=[profile, preference]),
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
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is False
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_consolidate_skips_rewrite_that_drops_fact_anchors():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = (
        "User's name is Bini. User works at Hooh. User's name is Binalfew. User is a developer."
    )

    rewrite = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="profile",
                summary=(
                    "Bini (Binalfew) is a software developer who builds mobile apps "
                    "and backend services for Recall."
                ),
                confidence=0.9,
            )
        ]
    )

    _, session_locals = _consolidation_sessions()
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
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
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is False
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_consolidate_upserts_without_embedding_when_vector_missing():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    updated = SimpleNamespace(
        type="profile",
        text="Bini (Binalfew) is a software developer with backend and mobile experience",
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

    _, session_locals = _consolidation_sessions(count=2)
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
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
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    assert updated.embedding is None


@pytest.mark.asyncio
async def test_consolidate_stores_embedding_when_vector_present():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    updated = SimpleNamespace(
        type="profile",
        text="Bini (Binalfew) is a software developer with backend and mobile experience",
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

    _, session_locals = _consolidation_sessions(count=2)
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
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
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    assert updated.embedding == vector
    assert updated.embedding_json == "[0.1,0.2,0.3]"


@pytest.mark.asyncio
async def test_consolidate_releases_db_before_llm():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    session = AsyncMock()
    session.commit = AsyncMock()
    db_open_during_rewrite: list[bool] = []

    class _TrackingSessionCM(_FakeSessionCM):
        def __init__(self) -> None:
            super().__init__(session)
            self.open = False

        async def __aenter__(self) -> AsyncMock:
            self.open = True
            return await super().__aenter__()

        async def __aexit__(self, *args: object) -> None:
            self.open = False
            await super().__aexit__(*args)

    load_cm = _TrackingSessionCM()
    apply_cm = _TrackingSessionCM()

    async def fake_rewrite(*_args: object, **_kwargs: object) -> None:
        db_open_during_rewrite.append(load_cm.open or apply_cm.open)
        return None

    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=[load_cm, apply_cm],
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(return_value=[memory]),
        ),
        patch(
            "app.background.memory_consolidation.litellm_gateway.rewrite_memory_sections",
            AsyncMock(side_effect=fake_rewrite),
        ),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is False
    assert db_open_during_rewrite == [False]
    assert session.commit.await_count == 1
