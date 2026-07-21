import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.background.memory_extraction import extract_and_store_memories
from app.core.config import Settings
from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult
from app.services.memory import embedding_text_hash


class _FakeSessionCM:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _extraction_sessions(*, count: int = 1) -> tuple[AsyncMock, list[_FakeSessionCM]]:
    session = AsyncMock()
    session.commit = AsyncMock()
    return session, [_FakeSessionCM(session) for _ in range(count)]


@pytest.fixture
def _real_memory_lock():
    """Opt a test out of the always-free lock stub below, to exercise the
    real acquire_memory_write_lock/release_memory_write_lock against a real
    (fake) Redis backend — see
    test_extraction_and_consolidation_do_not_race_the_same_user."""
    return True


@pytest.fixture(autouse=True)
def _memory_write_lock_always_free(request: pytest.FixtureRequest):
    """extract_and_store_memories now acquires memwrite:{user_id} before its
    read-modify-write section (guards against a concurrent consolidation
    pass racing it). Most of these tests exercise extraction logic, not
    Redis locking, so default the lock to always-acquired."""
    if "_real_memory_lock" in request.fixturenames:
        yield
        return
    with (
        patch(
            "app.background.memory_extraction.acquire_memory_write_lock",
            AsyncMock(return_value=True),
        ),
        patch("app.background.memory_extraction.release_memory_write_lock", AsyncMock()),
    ):
        yield


@pytest.mark.asyncio
async def test_extract_and_store_all_sections_below_confidence_skips_upsert():
    """When every extracted section falls below memory_min_confidence, the
    function must return before touching the DB at all — not just filter
    down to a partial write (already covered by
    test_extract_and_store_filters_confidence in test_services.py)."""
    settings = Settings(memory_min_confidence=0.7)
    extraction = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(type="fact", summary="Low conf fact one.", confidence=0.2),
            MemorySectionItem(type="fact", summary="Low conf fact two.", confidence=0.3),
        ]
    )
    upsert = AsyncMock()
    _, session_locals = _extraction_sessions()

    with (
        patch("app.background.memory_extraction.SessionLocal", side_effect=session_locals),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", upsert),
    ):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript="chat"
        )

    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_and_store_drops_section_with_empty_summary_after_normalize():
    """A summary that normalizes to an empty string (e.g. all punctuation)
    must be dropped, not upserted as a blank memory row."""
    settings = Settings(memory_min_confidence=0.4)
    extraction = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(type="fact", summary="...", confidence=0.9),
            MemorySectionItem(type="fact", summary="Uses Vim daily.", confidence=0.9),
        ]
    )
    upsert = AsyncMock()
    _, session_locals = _extraction_sessions(count=2)

    with (
        patch("app.background.memory_extraction.SessionLocal", side_effect=session_locals),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", upsert),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.services.home.invalidate_home_cache", AsyncMock()),
    ):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript="chat"
        )

    upsert.assert_awaited_once()
    items = upsert.call_args.kwargs["items"]
    assert len(items) == 1
    assert items[0][1].startswith("As of ")
    assert items[0][1].endswith("Uses Vim daily")


@pytest.mark.asyncio
async def test_extract_rejects_rewrite_that_drops_prior_anchors():
    """Whole-section extraction must not upsert a rewrite that drops stable
    fact anchors — same preservation gate consolidation already uses."""
    settings = Settings(memory_min_confidence=0.4)
    prior = "User's name is Bini. User works at Hooh. User is a developer."
    extraction = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="profile",
                summary="Bini is a software developer building mobile apps.",
                confidence=0.95,
            )
        ]
    )
    upsert = AsyncMock()
    existing = [SimpleNamespace(type="profile", text=prior)]
    _, session_locals = _extraction_sessions()

    with (
        patch("app.background.memory_extraction.SessionLocal", side_effect=session_locals),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(return_value=existing),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", upsert),
    ):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript="I build apps"
        )

    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_accepts_rewrite_that_preserves_anchors_and_adds_fact():
    settings = Settings(memory_min_confidence=0.4)
    prior = "User's name is Bini. User works at Hooh. User is a developer."
    rewritten = "Bini is a developer at Hooh building Recall."
    extraction = MemorySectionUpdateResult(
        sections=[MemorySectionItem(type="profile", summary=rewritten, confidence=0.95)]
    )
    upsert = AsyncMock()
    existing = [SimpleNamespace(type="profile", text=prior)]
    _, session_locals = _extraction_sessions(count=2)

    with (
        patch("app.background.memory_extraction.SessionLocal", side_effect=session_locals),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(side_effect=[existing, []]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", upsert),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.services.home.invalidate_home_cache", AsyncMock()),
    ):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript="I am building Recall"
        )

    upsert.assert_awaited_once()
    items = upsert.call_args.kwargs["items"]
    assert len(items) == 1
    assert items[0][0] == "profile"
    assert items[0][1].startswith("As of ")
    assert "Bini" in items[0][1]
    assert "Hooh" in items[0][1]
    assert "Recall" in items[0][1]


@pytest.mark.asyncio
async def test_extract_and_store_stores_embedding_for_new_memory():
    """Full round trip: a newly-extracted section gets both the pgvector
    column and the JSON fallback populated, with a hash matching its text —
    the invariant every later staleness check depends on."""
    settings = Settings(memory_min_confidence=0.4)
    extraction = MemorySectionUpdateResult(
        sections=[MemorySectionItem(type="fact", summary="Owns a bicycle.", confidence=0.9)]
    )

    updated = SimpleNamespace(
        type="fact",
        text="Owns a bicycle",
        embedding=None,
        embedding_json=None,
        embedding_text_hash=None,
    )
    vector = [0.4, 0.5, 0.6]

    _, session_locals = _extraction_sessions(count=2)
    with (
        patch("app.background.memory_extraction.SessionLocal", side_effect=session_locals),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(side_effect=[[], [updated]]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.upsert_sections", AsyncMock()),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.services.home.invalidate_home_cache", AsyncMock()),
        patch("app.gateways.embedding_gateway.embed_text", AsyncMock(return_value=vector)),
        patch(
            "app.gateways.embedding_gateway.serialize_embedding",
            return_value="[0.4,0.5,0.6]",
        ),
    ):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript="chat"
        )

    assert updated.embedding == vector
    assert updated.embedding_json == "[0.4,0.5,0.6]"
    assert updated.embedding_text_hash == embedding_text_hash(updated.text)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_real_memory_lock")
async def test_extraction_and_consolidation_do_not_race_the_same_user(fake_redis):
    """Integration coverage for the PR 1 fix: extraction and consolidation
    triggered back-to-back for the SAME user must not both win the
    memwrite:{user_id} lock — exactly one performs the write, the other
    detects the lock is held and skips. Runs the REAL
    acquire_memory_write_lock/release_memory_write_lock against a real (fake)
    Redis backend, not the always-free stub the other tests in this file use."""
    from app.background.memory_consolidation import consolidate_user_memory_sections

    user_id = uuid4()

    # Repeated-sentence text so consolidation's deterministic dedupe pre-pass
    # fires without needing to mock merge_memory_section too.
    messy_text = "Prefers concise answers. Prefers concise answers. Prefers concise answers."
    shared_memory = SimpleNamespace(
        type="preference",
        text=messy_text,
        embedding=[0.1, 0.2, 0.3],
        embedding_json="[0.1,0.2,0.3]",
        embedding_text_hash=embedding_text_hash(messy_text),
    )

    extraction_result = MemorySectionUpdateResult(
        sections=[MemorySectionItem(type="fact", summary="Uses Vim daily.", confidence=0.9)]
    )

    async def _slow_revise(*_args: object, **_kwargs: object) -> MemorySectionUpdateResult:
        # Forces a genuine event-loop yield while extraction still holds the
        # lock, so consolidation's concurrent acquire attempt actually lands
        # mid-critical-section instead of asyncio.gather happening to run
        # one coroutine to full completion (acquire -> work -> release)
        # before the other ever starts.
        await asyncio.sleep(0.05)
        return extraction_result

    upsert = AsyncMock()

    extraction_session, _ = _extraction_sessions()
    consolidation_session = AsyncMock()
    consolidation_session.commit = AsyncMock()

    with (
        patch("app.services.memory.get_redis_client", return_value=fake_redis),
        patch(
            "app.background.memory_extraction.SessionLocal",
            side_effect=lambda: _FakeSessionCM(extraction_session),
        ),
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=lambda: _FakeSessionCM(consolidation_session),
        ),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.repositories.memories.list_for_user",
            AsyncMock(return_value=[shared_memory]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_sections",
            AsyncMock(side_effect=_slow_revise),
        ),
        patch("app.repositories.memories.upsert_sections", upsert),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.background.memory_consolidation.invalidate_memory_block", AsyncMock()),
        patch("app.services.home.invalidate_home_cache", AsyncMock()),
    ):
        await asyncio.gather(
            extract_and_store_memories(
                Settings(memory_min_confidence=0.4),
                user_id=user_id,
                chat_id=uuid4(),
                transcript="chat",
            ),
            consolidate_user_memory_sections(Settings(memory_min_confidence=0.4), user_id=user_id),
        )

    # Exactly one of the two write paths actually ran — the other saw the
    # lock held and skipped entirely, rather than both silently overwriting
    # each other's section text.
    assert upsert.await_count == 1
