import asyncio
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.background.memory_extraction import extract_and_store_memories
from app.core.config import Settings
from app.models.schemas import MemoryFactOp, MemoryFactUpdateResult
from app.models.schemas.common import MemoryType
from app.repositories.memory_writes import MemoryFactWrite
from app.services.memory import embedding_text_hash

_CANDIDATE = "I like using Vim every day at work."


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


def _ops(*ops: MemoryFactOp) -> MemoryFactUpdateResult:
    return MemoryFactUpdateResult(ops=list(ops))


def _add(memory_type: MemoryType, text: str, confidence: float = 0.9) -> MemoryFactOp:
    return MemoryFactOp(op="add", type=memory_type, text=text, confidence=confidence)


def _user() -> MagicMock:
    return MagicMock(memory_enabled=True, memory_include_sensitive=False)


@pytest.fixture
def _real_memory_lock():
    return True


@pytest.fixture(autouse=True)
def _memory_persistence_gate_enabled():
    with patch("app.repositories.memories.lock_memory_enabled", AsyncMock(return_value=True)):
        yield


@pytest.fixture
def embedding_write():
    with patch("app.repositories.memories.update_embedding_if_current", AsyncMock()) as write:
        yield write


@pytest.fixture(autouse=True)
def _memory_extract_backlog_noop():
    with (
        patch(
            "app.services.memory.extract_backlog.messages_repo.list_user_contents_since",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.memory.extract_backlog.get_redis_client",
            MagicMock(return_value=AsyncMock(get=AsyncMock(return_value=None))),
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def _memory_write_lock_always_free(request: pytest.FixtureRequest):
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


@contextmanager
def _extract_patches(
    *,
    session_locals: list[_FakeSessionCM],
    extraction: MemoryFactUpdateResult | None,
    apply: AsyncMock,
    listed: list | None = None,
    user: MagicMock | None = None,
):
    with ExitStack() as stack:
        stack.enter_context(
            patch("app.background.memory_extraction.SessionLocal", side_effect=session_locals)
        )
        stack.enter_context(
            patch(
                "app.background.memory_extraction.users_repo.get_by_id",
                AsyncMock(return_value=user or _user()),
            )
        )
        stack.enter_context(
            patch(
                "app.background.memory_extraction.memories_repo.list_for_user",
                AsyncMock(return_value=listed or []),
            )
        )
        stack.enter_context(
            patch(
                "app.background.memory_extraction.memory_llm.revise_memory_facts",
                AsyncMock(return_value=extraction),
            )
        )
        stack.enter_context(patch("app.background.memory_extraction.apply_memory_facts", apply))
        yield


@pytest.mark.asyncio
async def test_extract_and_store_all_sections_below_confidence_skips_upsert():
    settings = Settings(memory_min_confidence=0.7)
    extraction = _ops(
        _add("fact", "Low conf fact one.", 0.2),
        _add("fact", "Low conf fact two.", 0.3),
    )
    apply = AsyncMock()
    _, session_locals = _extraction_sessions()

    with _extract_patches(session_locals=session_locals, extraction=extraction, apply=apply):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript=_CANDIDATE
        )

    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_skips_when_user_missing():
    settings = Settings(memory_min_confidence=0.4)
    apply = AsyncMock()
    revise = AsyncMock()
    _, session_locals = _extraction_sessions()

    with (
        patch("app.background.memory_extraction.SessionLocal", side_effect=session_locals),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_facts",
            revise,
        ),
        patch("app.background.memory_extraction.apply_memory_facts", apply),
    ):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript=_CANDIDATE
        )

    apply.assert_not_awaited()
    revise.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_skips_non_candidate_small_talk():
    apply = AsyncMock()
    revise = AsyncMock()
    _, session_locals = _extraction_sessions()
    with (
        patch("app.background.memory_extraction.SessionLocal", side_effect=session_locals),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=_user()),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch("app.background.memory_extraction.memory_llm.revise_memory_facts", revise),
        patch("app.background.memory_extraction.apply_memory_facts", apply),
    ):
        await extract_and_store_memories(
            Settings(), user_id=uuid4(), chat_id=uuid4(), transcript="hey there"
        )

    revise.assert_not_awaited()
    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_and_store_drops_section_with_empty_summary_after_normalize():
    settings = Settings(memory_min_confidence=0.4)
    extraction = _ops(
        _add("fact", "..."),
        _add("fact", "Uses Vim daily."),
    )
    apply = AsyncMock()
    _, session_locals = _extraction_sessions()

    with _extract_patches(session_locals=session_locals, extraction=extraction, apply=apply):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript=_CANDIDATE
        )

    apply.assert_awaited_once()
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    assert len(writes) == 1
    assert writes[0].text == "Uses Vim daily"
    assert not writes[0].text.startswith("As of ")


@pytest.mark.asyncio
async def test_extract_explicit_remember_adds_short_preference():
    settings = Settings(memory_min_confidence=0.4)
    pref_id = uuid4()
    prior = (
        "Bini prefers varied learning formats for English vocabulary sessions, "
        "alternating between teach then use, use then define, and occasional "
        "multiple-choice questions"
    )
    extraction = _ops(_add("preference", "Drinks oat milk."))
    apply = AsyncMock()
    _, session_locals = _extraction_sessions()

    with _extract_patches(
        session_locals=session_locals,
        extraction=extraction,
        apply=apply,
        listed=[SimpleNamespace(id=pref_id, type="preference", text=prior, status="active")],
    ):
        await extract_and_store_memories(
            settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="User: Remember that I drink oat milk.",
        )

    apply.assert_awaited_once()
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    assert len(writes) == 1
    assert writes[0].op == "add"
    assert "oat milk" in writes[0].text.lower()


@pytest.mark.asyncio
async def test_extract_and_store_deletes_fact_on_explicit_forget():
    settings = Settings(memory_min_confidence=0.4)
    fact_id = uuid4()
    extraction = _ops(
        MemoryFactOp(
            op="delete",
            type="fact",
            text="",
            confidence=0.9,
            match_text="Lives in Boston",
        )
    )
    apply = AsyncMock()
    _, session_locals = _extraction_sessions()

    with _extract_patches(
        session_locals=session_locals,
        extraction=extraction,
        apply=apply,
        listed=[SimpleNamespace(id=fact_id, type="fact", text="Lives in Boston", status="active")],
    ):
        await extract_and_store_memories(
            settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="User: Please forget that I live in Boston",
        )

    apply.assert_awaited_once()
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    assert writes[0].op == "delete"
    assert writes[0].match_text == "Lives in Boston"


@pytest.mark.asyncio
async def test_extract_forget_does_not_clear_unrelated_nonempty_sections():
    settings = Settings(memory_min_confidence=0.4)
    fact_id = uuid4()
    pref_id = uuid4()
    extraction = _ops(
        MemoryFactOp(
            op="delete",
            type="fact",
            text="",
            confidence=0.9,
            match_text="Lives in Boston",
        ),
        _add("preference", "Tea."),
    )
    apply = AsyncMock()
    _, session_locals = _extraction_sessions()

    with _extract_patches(
        session_locals=session_locals,
        extraction=extraction,
        apply=apply,
        listed=[
            SimpleNamespace(id=fact_id, type="fact", text="Lives in Boston", status="active"),
            SimpleNamespace(
                id=pref_id,
                type="preference",
                text="Drinks strong coffee every morning and afternoon.",
                status="active",
            ),
        ],
    ):
        await extract_and_store_memories(
            settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="User: Please forget that I live in Boston",
        )

    apply.assert_awaited_once()
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    assert {write.op for write in writes} == {"delete", "add"}
    assert any(write.op == "delete" and write.match_text == "Lives in Boston" for write in writes)
    assert any(write.op == "add" and "Tea" in write.text for write in writes)


@pytest.mark.asyncio
async def test_extract_applies_add_without_rewriting_unrelated_facts():
    settings = Settings(memory_min_confidence=0.4)
    prior = "User's name is Bini. User works at Hooh. User is a developer."
    extraction = _ops(_add("profile", "Bini is building Recall."))
    apply = AsyncMock()
    existing = [SimpleNamespace(id=uuid4(), type="profile", text=prior, status="active")]
    _, session_locals = _extraction_sessions()

    with _extract_patches(
        session_locals=session_locals,
        extraction=extraction,
        apply=apply,
        listed=existing,
    ):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript="I am building Recall"
        )

    apply.assert_awaited_once()
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    assert writes[0].op == "add"
    assert "Recall" in writes[0].text
    assert "Hooh" not in writes[0].text


@pytest.mark.asyncio
async def test_extract_skips_highly_sensitive_unless_remember_or_opt_in():
    settings = Settings(memory_min_confidence=0.4)
    extraction = _ops(
        MemoryFactOp(
            op="add",
            type="fact",
            text="User is Catholic.",
            confidence=0.9,
            sensitivity="highly_sensitive",
        )
    )
    apply = AsyncMock()
    _, session_locals = _extraction_sessions()
    with _extract_patches(session_locals=session_locals, extraction=extraction, apply=apply):
        await extract_and_store_memories(
            settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="I am Catholic.",
        )
    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_persists_highly_sensitive_on_explicit_remember():
    settings = Settings(memory_min_confidence=0.4)
    extraction = _ops(
        MemoryFactOp(
            op="add",
            type="fact",
            text="User is Catholic.",
            confidence=0.9,
            sensitivity="highly_sensitive",
        )
    )
    apply = AsyncMock()
    _, session_locals = _extraction_sessions()
    with _extract_patches(session_locals=session_locals, extraction=extraction, apply=apply):
        await extract_and_store_memories(
            settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="User: Remember that I am Catholic.",
        )
    apply.assert_awaited_once()
    writes: list[MemoryFactWrite] = apply.await_args.kwargs["writes"]
    assert writes[0].sensitivity == "highly_sensitive"


@pytest.mark.asyncio
async def test_extract_and_store_stores_embedding_for_new_memory(embedding_write):
    settings = Settings(memory_min_confidence=0.4)
    extraction = _ops(_add("fact", "Owns a bicycle."))
    memory_id = uuid4()
    listed = SimpleNamespace(
        id=memory_id,
        type="fact",
        text="Owns a bicycle",
        status="active",
        embedding=None,
        embedding_json=None,
        embedding_text_hash=None,
    )
    vector = [0.4, 0.5, 0.6]
    apply_writes = AsyncMock(return_value=[memory_id])
    session, session_locals = _extraction_sessions(count=3)
    with (
        patch("app.background.memory_extraction.SessionLocal", side_effect=session_locals),
        patch(
            "app.background.memory_extraction.users_repo.get_by_id",
            AsyncMock(return_value=_user()),
        ),
        patch(
            "app.background.memory_extraction.memories_repo.list_for_user",
            AsyncMock(side_effect=[[], [listed]]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_facts",
            AsyncMock(return_value=extraction),
        ),
        patch("app.background.memory_extraction.memories_repo.apply_writes", apply_writes),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.services.home.invalidate_home_cache", AsyncMock()),
        patch("app.gateways.embedding_gateway.embed_text", AsyncMock(return_value=vector)),
        patch(
            "app.gateways.embedding_gateway.serialize_embedding",
            return_value="[0.4,0.5,0.6]",
        ),
    ):
        await extract_and_store_memories(
            settings, user_id=uuid4(), chat_id=uuid4(), transcript=_CANDIDATE
        )

    embedding_write.assert_awaited_once()
    assert embedding_write.await_args.args[2:] == (
        memory_id,
        listed.text,
        vector,
        "[0.4,0.5,0.6]",
        embedding_text_hash(listed.text),
    )
    assert embedding_write.await_args.kwargs == {"commit": False}


@pytest.mark.asyncio
@pytest.mark.usefixtures("_real_memory_lock")
async def test_extraction_and_consolidation_do_not_race_the_same_user(fake_redis):
    from app.background.memory_consolidation import consolidate_user_memory_sections

    user_id = uuid4()
    text = "Prefers concise answers."
    keep = SimpleNamespace(
        id=uuid4(),
        type="preference",
        text=text,
        status="active",
        last_confirmed_at=None,
        updated_at=0,
        embedding=[0.1, 0.2, 0.3],
        embedding_json="[0.1,0.2,0.3]",
        embedding_text_hash=embedding_text_hash(text),
    )
    extra = SimpleNamespace(
        id=uuid4(),
        type="preference",
        text=text,
        status="active",
        last_confirmed_at=None,
        updated_at=0,
        embedding=[0.1, 0.2, 0.3],
        embedding_json="[0.1,0.2,0.3]",
        embedding_text_hash=embedding_text_hash(text),
    )
    extraction_result = _ops(_add("fact", "Uses Vim daily."))

    async def _slow_revise(*_args: object, **_kwargs: object) -> MemoryFactUpdateResult:
        await asyncio.sleep(0.05)
        return extraction_result

    apply = AsyncMock()
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
            AsyncMock(return_value=_user()),
        ),
        patch(
            "app.background.memory_consolidation.users_repo.get_by_id",
            AsyncMock(return_value=_user()),
        ),
        patch(
            "app.repositories.memories.list_for_user",
            AsyncMock(return_value=[keep, extra]),
        ),
        patch(
            "app.background.memory_extraction.memory_llm.revise_memory_facts",
            AsyncMock(side_effect=_slow_revise),
        ),
        patch("app.services.memory.extraction_workflow.apply_memory_facts", apply),
        patch("app.services.memory.consolidation_workflow.apply_memory_facts", apply),
        patch("app.services.memory.invalidate_memory_block", AsyncMock()),
        patch("app.services.home.invalidate_home_cache", AsyncMock()),
    ):
        await asyncio.gather(
            extract_and_store_memories(
                Settings(memory_min_confidence=0.4),
                user_id=user_id,
                chat_id=uuid4(),
                transcript=_CANDIDATE,
            ),
            consolidate_user_memory_sections(Settings(memory_min_confidence=0.4), user_id=user_id),
        )

    assert apply.await_count == 1
