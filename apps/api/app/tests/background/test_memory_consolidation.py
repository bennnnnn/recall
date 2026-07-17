from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.background.memory_consolidation import consolidate_user_memory_sections
from app.core.config import Settings
from app.models.schemas import MemorySectionItem
from app.services.memory import embedding_text_hash


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


@pytest.fixture(autouse=True)
def _memory_write_lock_always_free():
    """consolidate_user_memory_sections now acquires memwrite:{user_id}
    before its read-modify-write section (guards against a concurrent
    extraction pass racing it). These tests exercise consolidation logic,
    not Redis locking, so default the lock to always-acquired;
    test_consolidate_skips_when_write_lock_held overrides this to test the
    lock-held path specifically."""
    with (
        patch(
            "app.background.memory_consolidation.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ),
        patch("app.background.memory_consolidation.release_memory_write_lock", AsyncMock()),
    ):
        yield


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
async def test_consolidate_skips_when_write_lock_held():
    """BUG FIX: without a lock, consolidation and a concurrently-running
    extraction pass for the same user can both read the same prior section
    text and whichever commits last silently discards the other's write.
    When memwrite:{user_id} is already held (by extraction or another
    consolidation), this run must skip entirely — no LLM call, no DB write.

    Uses plain (non-raising) mocks and asserts they were never awaited,
    rather than side_effect=AssertionError, because
    consolidate_user_memory_sections swallows all internal exceptions
    (Golden Rule 4) — a raised AssertionError would just be caught and
    logged, silently passing even pre-fix."""
    user_id = uuid4()
    list_for_user = AsyncMock()
    merge = AsyncMock()
    with (
        patch(
            "app.background.memory_consolidation.acquire_memory_write_lock",
            AsyncMock(return_value=False),
        ),
        patch("app.background.memory_consolidation.memories_repo.list_for_user", list_for_user),
        patch("app.background.memory_consolidation.memory_llm.merge_memory_section", merge),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is False
    list_for_user.assert_not_awaited()
    merge.assert_not_awaited()


@pytest.mark.asyncio
async def test_consolidate_merges_messy_sections():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    merged = MemorySectionItem(
        type="profile",
        summary=(
            "Bini (Binalfew) is a software developer who builds mobile apps "
            "and backend services for Recall."
        ),
        confidence=0.9,
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
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(return_value=merged),
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
async def test_consolidate_skips_suspiciously_short_merge():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    merged = MemorySectionItem(
        type="profile",
        summary="Bini.",
        confidence=0.9,
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
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(return_value=merged),
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
async def test_consolidate_applies_only_sections_that_need_merge():
    """Clean sections are left alone; only messy ones are merged."""
    user_id = uuid4()
    profile = AsyncMock()
    profile.type = "profile"
    profile.text = "User's name is Bini. User's name is Binalfew. User is a developer."
    preference = AsyncMock()
    preference.type = "preference"
    preference.text = "Prefers concise answers."

    merged = MemorySectionItem(
        type="profile",
        summary=(
            "Bini (Binalfew) is a software developer who builds mobile apps "
            "and backend services for Recall."
        ),
        confidence=0.9,
    )

    _, session_locals = _consolidation_sessions(count=2)
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
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(return_value=merged),
        ) as merge,
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

    assert changed is True
    assert merge.await_count == 1
    assert merge.await_args.kwargs["section_type"] == "profile"
    assert len(upsert.call_args.kwargs["items"]) == 1
    assert upsert.call_args.kwargs["items"][0][0] == "profile"


@pytest.mark.asyncio
async def test_consolidate_skips_merge_that_drops_fact_anchors():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = (
        "User's name is Bini. User works at Hooh. User's name is Binalfew. User is a developer."
    )

    merged = MemorySectionItem(
        type="profile",
        summary=(
            "Bini (Binalfew) is a software developer who builds mobile apps "
            "and backend services for Recall."
        ),
        confidence=0.9,
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
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(return_value=merged),
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
        embedding_text_hash=None,
    )

    merged = MemorySectionItem(
        type="profile",
        summary=updated.text,
        confidence=0.9,
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
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(return_value=merged),
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
        embedding_text_hash=None,
    )

    merged = MemorySectionItem(
        type="profile",
        summary=updated.text,
        confidence=0.9,
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
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(return_value=merged),
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
    assert updated.embedding_text_hash == embedding_text_hash(updated.text)


@pytest.mark.asyncio
async def test_consolidate_reembeds_stale_section_even_if_untouched_this_pass():
    """BUG FIX regression: a section that consolidation didn't merge this pass
    (e.g. because a prior embed attempt failed after its own text change) must
    still be caught by the embedding_text_hash mismatch check, not left stale
    forever just because this pass's `rows` didn't include it."""
    user_id = uuid4()
    profile = AsyncMock()
    profile.type = "profile"
    profile.text = "User's name is Bini. User's name is Binalfew. User is a developer."
    preference = AsyncMock()
    preference.type = "preference"
    preference.text = "Prefers concise answers."

    merged = MemorySectionItem(
        type="profile",
        summary=(
            "Bini (Binalfew) is a software developer who builds mobile apps "
            "and backend services for Recall."
        ),
        confidence=0.9,
    )

    updated_profile = SimpleNamespace(
        type="profile",
        text=merged.summary,
        embedding=[0.1, 0.2, 0.3],
        embedding_json="[0.1,0.2,0.3]",
        embedding_text_hash=embedding_text_hash(merged.summary),
    )
    # Simulates a section left over with a stale hash from a previous failed
    # embed attempt — untouched by this consolidation pass's `rows`.
    updated_preference = SimpleNamespace(
        type="preference",
        text=preference.text,
        embedding=[0.4, 0.5, 0.6],
        embedding_json="[0.4,0.5,0.6]",
        embedding_text_hash="stale-hash-from-a-failed-embed",
    )

    vector = [0.7, 0.8, 0.9]

    _, session_locals = _consolidation_sessions(count=2)
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(
                side_effect=[
                    [profile, preference],
                    [updated_profile, updated_preference],
                ]
            ),
        ),
        patch(
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(return_value=merged),
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
            return_value="[0.7,0.8,0.9]",
        ),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    # The stale preference section got re-embedded even though it wasn't
    # part of this pass's merge output.
    assert updated_preference.embedding == vector
    assert updated_preference.embedding_json == "[0.7,0.8,0.9]"
    assert updated_preference.embedding_text_hash == embedding_text_hash(preference.text)


@pytest.mark.asyncio
async def test_consolidate_releases_db_before_llm():
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "profile"
    memory.text = "User's name is Bini. User's name is Binalfew. User is a developer."

    session = AsyncMock()
    session.commit = AsyncMock()
    db_open_during_merge: list[bool] = []

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

    async def fake_merge(*_args: object, **_kwargs: object) -> None:
        db_open_during_merge.append(load_cm.open or apply_cm.open)
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
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(side_effect=fake_merge),
        ),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is False
    assert db_open_during_merge == [False]
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_consolidate_deterministic_dedupe_skips_llm():
    """Exact duplicate sentences can be collapsed without calling the model."""
    user_id = uuid4()
    memory = AsyncMock()
    memory.type = "preference"
    memory.text = "Prefers concise answers. Prefers concise answers. Prefers concise answers."

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
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(),
        ) as merge,
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
            AsyncMock(return_value=None),
        ),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    merge.assert_not_awaited()
    assert upsert.call_args.kwargs["items"][0][1] == "Prefers concise answers"
