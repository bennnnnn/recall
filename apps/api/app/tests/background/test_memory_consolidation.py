from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.background.memory_consolidation import consolidate_user_memory_sections
from app.core.config import Settings
from app.models.schemas import MemorySectionItem
from app.repositories.memory_writes import MemoryFactWrite
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


def _fact(
    *,
    memory_id=None,
    memory_type: str = "profile",
    text: str,
    status: str = "active",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=memory_id or uuid4(),
        type=memory_type,
        text=text,
        status=status,
        last_confirmed_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        embedding=None,
        embedding_json=None,
        embedding_text_hash=None,
    )


@pytest.fixture(autouse=True)
def _memory_persistence_gate_enabled():
    with patch("app.repositories.memories.lock_memory_enabled", AsyncMock(return_value=True)):
        yield


@pytest.fixture
def embedding_write():
    with patch("app.repositories.memories.update_embedding_if_current", AsyncMock()) as write:
        yield write


@pytest.fixture(autouse=True)
def _memory_write_lock_always_free():
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
    memory = _fact(text="Bini is a software engineer at Hooh.")
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
async def test_consolidate_deletes_exact_duplicate_without_llm():
    user_id = uuid4()
    text = "Prefers concise answers."
    keep = _fact(memory_type="preference", text=text)
    extra = _fact(memory_type="preference", text=text)
    apply = AsyncMock()
    merge = AsyncMock()
    _, session_locals = _consolidation_sessions()
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(return_value=[keep, extra]),
        ),
        patch("app.background.memory_consolidation.memory_llm.merge_memory_section", merge),
        patch("app.background.memory_consolidation.apply_memory_facts", apply),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    merge.assert_not_awaited()
    apply.assert_awaited_once()
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    assert len(writes) == 1
    assert writes[0].op == "delete"
    assert writes[0].match_text == text


@pytest.mark.asyncio
async def test_consolidate_merges_near_duplicate_pair():
    user_id = uuid4()
    keep = _fact(text="Bini is a developer at Hooh.")
    extra = _fact(text="Bini is a developer at Hooh now.")
    extra.last_confirmed_at = datetime(2026, 1, 1, tzinfo=UTC)
    keep.last_confirmed_at = datetime(2026, 6, 1, tzinfo=UTC)
    merged = MemorySectionItem(
        type="profile",
        summary="Bini is a developer at Hooh today.",
        confidence=0.9,
    )
    apply = AsyncMock()
    _, session_locals = _consolidation_sessions()
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(return_value=[keep, extra]),
        ),
        patch(
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(return_value=merged),
        ),
        patch("app.background.memory_consolidation.apply_memory_facts", apply),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    ops = {write.op for write in writes}
    assert "delete" in ops
    assert any(write.op == "update" and "today" in write.text for write in writes)


@pytest.mark.asyncio
async def test_consolidate_keeps_keeper_when_merge_drops_anchors():
    user_id = uuid4()
    keep = _fact(text="Bini works at Hooh and lives in Oakland.")
    extra = _fact(text="Bini works at Hooh and lives in Oakland now.")
    merged = MemorySectionItem(type="profile", summary="Bini.", confidence=0.9)
    apply = AsyncMock()
    _, session_locals = _consolidation_sessions()
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(return_value=[keep, extra]),
        ),
        patch(
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(return_value=merged),
        ),
        patch("app.background.memory_consolidation.apply_memory_facts", apply),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    assert all(write.op == "delete" for write in writes)


@pytest.mark.asyncio
async def test_consolidate_applies_only_duplicate_types():
    user_id = uuid4()
    profile_a = _fact(text="Bini is a developer at Hooh.")
    profile_b = _fact(text="Bini is a developer at Hooh.")
    preference = _fact(memory_type="preference", text="Prefers concise answers.")
    apply = AsyncMock()
    merge = AsyncMock()
    _, session_locals = _consolidation_sessions()
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(return_value=[profile_a, profile_b, preference]),
        ),
        patch("app.background.memory_consolidation.memory_llm.merge_memory_section", merge),
        patch("app.background.memory_consolidation.apply_memory_facts", apply),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    merge.assert_not_awaited()
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    assert all(write.type == "profile" for write in writes)


@pytest.mark.asyncio
async def test_consolidate_stores_embedding_when_vector_present(embedding_write):
    user_id = uuid4()
    text = "Prefers concise answers."
    keep = _fact(memory_type="preference", text=text)
    extra = _fact(memory_type="preference", text=text)
    listed = SimpleNamespace(
        id=keep.id,
        type="preference",
        text=text,
        status="active",
        embedding=None,
        embedding_json=None,
        embedding_text_hash=None,
    )
    vector = [0.1, 0.2, 0.3]
    session, session_locals = _consolidation_sessions(count=3)
    with (
        patch(
            "app.background.memory_consolidation.SessionLocal",
            side_effect=session_locals,
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.list_for_user",
            AsyncMock(side_effect=[[keep, extra], [listed]]),
        ),
        patch(
            "app.background.memory_consolidation.memories_repo.apply_writes",
            AsyncMock(return_value=[keep.id]),
        ),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.services.home.invalidate_home_cache", AsyncMock()),
        patch("app.gateways.embedding_gateway.embed_text", AsyncMock(return_value=vector)),
        patch(
            "app.gateways.embedding_gateway.serialize_embedding",
            return_value="[0.1,0.2,0.3]",
        ),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    embedding_write.assert_awaited_once_with(
        session,
        user_id,
        keep.id,
        listed.text,
        vector,
        "[0.1,0.2,0.3]",
        embedding_text_hash(listed.text),
        commit=False,
    )


@pytest.mark.asyncio
async def test_consolidate_releases_db_before_llm():
    user_id = uuid4()
    keep = _fact(text="Bini is a developer at Hooh.")
    extra = _fact(text="Bini is a developer at Hooh now.")
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
            AsyncMock(return_value=[keep, extra]),
        ),
        patch(
            "app.background.memory_consolidation.memory_llm.merge_memory_section",
            AsyncMock(side_effect=fake_merge),
        ),
        patch("app.background.memory_consolidation.apply_memory_facts", AsyncMock()),
    ):
        changed = await consolidate_user_memory_sections(Settings(), user_id=user_id)

    assert changed is True
    assert db_open_during_merge == [False]
    session.commit.assert_not_awaited()
