from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.background.memory_consolidation import consolidate_user_memory_sections
from app.core.config import Settings
from app.models.orm import Memory
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
        patch(
            "app.background.memory_consolidation.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
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
async def test_consolidate_skips_when_memory_disabled():
    """When memory_enabled is off, consolidation must no-op (no LLM / no write)."""
    user_id = uuid4()
    list_for_user = AsyncMock()
    merge = AsyncMock()
    _, session_locals = _consolidation_sessions()
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=False)),
        ),
        patch("app.background.memory_consolidation.memories_repo.list_for_user", list_for_user),
        patch("app.background.memory_consolidation.memory_llm.merge_memory_section", merge),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is False
    list_for_user.assert_not_awaited()
    merge.assert_not_awaited()


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

    assert changed == "skipped_lock"
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

    _, session_locals = _consolidation_sessions(count=3)
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
            "app.services.memory.invalidate_memory_block",
            AsyncMock(),
        ) as invalidate_memory,
        patch(
            "app.services.home.invalidate_home_cache",
            AsyncMock(),
        ) as invalidate_home,
        patch(
            "app.gateways.embedding_gateway.embed_text",
            AsyncMock(return_value=[0.1, 0.2, 0.3]),
        ),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    expected_body = (
        "Bini (Binalfew) is a software developer who builds mobile apps "
        "and backend services for Recall"
    )
    assert changed is True
    upsert.assert_awaited_once()
    written = upsert.call_args.kwargs["items"][0][1]
    assert written.startswith("As of ")
    assert written.endswith(expected_body)
    invalidate_memory.assert_awaited_once_with(user_id)
    invalidate_home.assert_awaited_once_with(user_id)


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

    _, session_locals = _consolidation_sessions(count=3)
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
            "app.services.memory.invalidate_memory_block",
            AsyncMock(),
        ),
        patch(
            "app.services.home.invalidate_home_cache",
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
        id=uuid4(),
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
            "app.services.memory.invalidate_memory_block",
            AsyncMock(),
        ),
        patch(
            "app.services.home.invalidate_home_cache",
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

    memory_id = uuid4()
    listed = SimpleNamespace(
        id=memory_id,
        type="profile",
        text="Bini (Binalfew) is a software developer with backend and mobile experience",
        embedding=None,
        embedding_json=None,
        embedding_text_hash=None,
    )
    # Phase-3 session.get(Memory, id) re-fetches the row; the vector lands here.
    fetched = SimpleNamespace(
        id=memory_id,
        type="profile",
        text=listed.text,
        embedding=None,
        embedding_json=None,
        embedding_text_hash=None,
    )

    merged = MemorySectionItem(
        type="profile",
        summary=listed.text,
        confidence=0.9,
    )
    vector = [0.1, 0.2, 0.3]

    session, session_locals = _consolidation_sessions(count=3)
    session.get = AsyncMock(return_value=fetched)
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(side_effect=[[memory], [listed]]),
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
            "app.services.memory.invalidate_memory_block",
            AsyncMock(),
        ),
        patch(
            "app.services.home.invalidate_home_cache",
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
    session.get.assert_awaited_with(Memory, memory_id)
    assert fetched.embedding == vector
    assert fetched.embedding_json == "[0.1,0.2,0.3]"
    assert fetched.embedding_text_hash == embedding_text_hash(fetched.text)
    # The phase-1 list row is detached when phase 1 closes its session — the
    # vector lands on the phase-3 re-fetch, not on `listed`.
    assert listed.embedding is None


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

    profile_id = uuid4()
    preference_id = uuid4()
    listed_profile = SimpleNamespace(
        id=profile_id,
        type="profile",
        text=merged.summary,
        embedding=[0.1, 0.2, 0.3],
        embedding_json="[0.1,0.2,0.3]",
        embedding_text_hash=embedding_text_hash(merged.summary),
    )
    # Simulates a section left over with a stale hash from a previous failed
    # embed attempt — untouched by this consolidation pass's `rows`.
    listed_preference = SimpleNamespace(
        id=preference_id,
        type="preference",
        text=preference.text,
        embedding=[0.4, 0.5, 0.6],
        embedding_json="[0.4,0.5,0.6]",
        embedding_text_hash="stale-hash-from-a-failed-embed",
    )
    # Phase-3 re-fetches by id; the vector lands here (only the stale
    # preference needs re-embedding — the profile's hash already matches).
    fetched_preference = SimpleNamespace(
        id=preference_id,
        type="preference",
        text=listed_preference.text,
        embedding=None,
        embedding_json=None,
        embedding_text_hash=None,
    )

    vector = [0.7, 0.8, 0.9]

    session, session_locals = _consolidation_sessions(count=3)
    session.get = AsyncMock(return_value=fetched_preference)
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
                    [listed_profile, listed_preference],
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
            "app.services.memory.invalidate_memory_block",
            AsyncMock(),
        ),
        patch(
            "app.services.home.invalidate_home_cache",
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
    assert fetched_preference.embedding == vector
    assert fetched_preference.embedding_json == "[0.7,0.8,0.9]"
    assert fetched_preference.embedding_text_hash == embedding_text_hash(preference.text)
    # The phase-1 list rows are detached; vectors land on the phase-3 re-fetches.
    assert listed_preference.embedding == [0.4, 0.5, 0.6]


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
    session.commit.assert_not_awaited()


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
            "app.services.memory.invalidate_memory_block",
            AsyncMock(),
        ),
        patch(
            "app.services.home.invalidate_home_cache",
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
    written = upsert.call_args.kwargs["items"][0][1]
    assert written.startswith("As of ")
    assert written.endswith("Prefers concise answers")
