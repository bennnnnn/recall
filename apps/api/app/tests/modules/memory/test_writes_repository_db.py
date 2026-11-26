"""PostgreSQL regressions for memory management versus stale background results."""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.models.orm import Memory
from app.modules.memory import repository as memories_repo
from app.repositories import users as users_repo
from app.tests.modules.memory.sections_support import upsert_sections


async def _make_user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["same", "new_text", "manual_edit", "delete", "wrong_owner"])
async def test_background_snapshot_preserves_manual_changes_and_ownership(db_session, change):
    user = await _make_user(db_session)
    row = Memory(
        user_id=user.id,
        type="fact",
        text="Old fact",
        embedding=[0.1] * 1536,
        embedding_text_hash="old-hash",
    )
    db_session.add(row)
    await db_session.flush()
    memory_id = row.id
    if change == "manual_edit":
        row.text = "Manual edit"
    elif change == "delete":
        await db_session.delete(row)
    await db_session.flush()

    await upsert_sections(
        db_session,
        user_id=uuid4() if change == "wrong_owner" else user.id,
        items=[("fact", "Old fact" if change == "same" else "Generated fact", 0.9, None)],
        expected_sections={"fact": (memory_id, "Old fact")},
    )

    if change == "delete":
        assert await memories_repo.list_for_user(db_session, user.id) == []
        return
    await db_session.refresh(row, attribute_names=["text", "embedding", "embedding_text_hash"])
    expected = {"manual_edit": "Manual edit", "new_text": "Generated fact"}.get(change, "Old fact")
    assert row.text == expected
    assert (row.embedding is None) == (change == "new_text")
    assert row.embedding_text_hash == (None if change == "new_text" else "old-hash")


@pytest.mark.asyncio
async def test_new_section_conflict_does_not_replace_competing_creation(db_session):
    user = await _make_user(db_session)
    for content in ["First fact", "Stale generated fact"]:
        await upsert_sections(
            db_session,
            user_id=user.id,
            items=[("fact", content, 0.9, None)],
            expected_sections={},
        )
    rows = await memories_repo.list_for_user(db_session, user.id)
    assert {row.text for row in rows} == {"First fact", "Stale generated fact"}


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False, None])
async def test_background_persistence_checks_current_account_preference(db_session, enabled):
    user = await _make_user(db_session)
    user.memory_enabled = bool(enabled)
    await db_session.flush()
    assert await memories_repo.lock_memory_enabled(
        db_session, user.id if enabled is not None else uuid4()
    ) is bool(enabled)


@pytest.mark.asyncio
@pytest.mark.parametrize("match", ["current", "stale_text", "wrong_owner", "deleted"])
async def test_background_embedding_only_updates_owned_current_text(db_session, match):
    user = await _make_user(db_session)
    row = Memory(user_id=user.id, type="fact", text="Current fact")
    db_session.add(row)
    await db_session.flush()
    memory_id = row.id
    if match == "deleted":
        await db_session.delete(row)
        await db_session.flush()
    await memories_repo.update_embedding_if_current(
        db_session,
        uuid4() if match == "wrong_owner" else user.id,
        memory_id,
        "Stale fact" if match == "stale_text" else "Current fact",
        [0.2] * 1536,
        "current-hash",
    )
    if match == "deleted":
        assert await memories_repo.list_for_user(db_session, user.id) == []
        return
    await db_session.refresh(row, attribute_names=["text", "embedding", "embedding_text_hash"])
    assert (row.embedding is not None) == (match == "current")
    assert row.embedding_text_hash == ("current-hash" if match == "current" else None)


@pytest.mark.asyncio
async def test_a_kept_near_duplicate_keeps_only_a_slot_its_text_answers(db_session):
    """The older fact kept by an earlier chat's line loses a slot filed by mistake and takes
    the one its text answers from the fact it replaces (Gemini review, #2539)."""
    user = await _make_user(db_session)
    kept = Memory(
        user_id=user.id, type="profile", text="User lives in Denver", slot="name",
        embedding=[0.1] * 1536,
    )  # fmt: skip
    gone = Memory(
        user_id=user.id, type="profile", text="User is based in Denver", slot="home",
        embedding=[0.1] * 1536,
    )  # fmt: skip
    db_session.add_all([kept, gone])
    await db_session.flush()

    retired = await memories_repo.retire_near_duplicates(
        db_session, user.id, [gone.id], min_similarity=0.9, new_wins=False
    )

    assert retired == 1
    assert (kept.status, kept.slot) == ("active", "home")
    assert gone.status == "superseded"


_JAN, _FEB, _MAR = (datetime(2026, month, 1, tzinfo=UTC) for month in (1, 2, 3))


def _denver(user_id, text, *, written, created=_JAN, **kw):
    return Memory(
        user_id=user_id, type="profile", text=text, embedding=[0.1] * 1536,
        created_at=created, last_confirmed_at=written, **kw,
    )  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.parametrize("backfilled_is_newer", [False, True])
async def test_a_backfilled_fact_said_again_keeps_the_one_written_last(
    db_session, backfilled_is_newer
):
    """A fact whose vector came late (its instruct pass ran out of time embedding) was never
    compared. Compared once backfilled, the one whose text was written last stays, whichever
    it is. A rewrite keeps the fact's ``created_at``: a fact made in January and rewritten in
    March is the newer of it and one made in February (#2599 review)."""
    user = await _make_user(db_session)
    backfilled = _denver(
        user.id, "User lives in Denver", written=_MAR if backfilled_is_newer else _FEB
    )
    other = _denver(
        user.id, "User is based in Denver", created=_FEB,
        written=_FEB if backfilled_is_newer else _MAR, importance=0.9,
    )  # fmt: skip
    db_session.add_all([backfilled, other])
    await db_session.flush()

    retired = await memories_repo.retire_near_duplicates(
        db_session, user.id, [backfilled.id], min_similarity=0.9, by_age=True
    )

    assert retired == 1
    kept, gone = (backfilled, other) if backfilled_is_newer else (other, backfilled)
    assert (kept.status, gone.status) == ("active", "superseded")
    assert kept.importance == 0.9


@pytest.mark.asyncio
async def test_two_backfilled_facts_retire_only_the_earlier(db_session):
    """Backfilled facts are compared with each other: the pair comes back both ways, and
    only the one written first goes."""
    user = await _make_user(db_session)
    earlier = _denver(user.id, "User lives in Denver", written=_FEB)
    later = _denver(user.id, "User is based in Denver", written=_MAR)
    db_session.add_all([earlier, later])
    await db_session.flush()

    retired = await memories_repo.retire_near_duplicates(
        db_session, user.id, [later.id, earlier.id], min_similarity=0.9, by_age=True
    )

    assert retired == 1
    assert (earlier.status, later.status) == ("superseded", "active")


@pytest.mark.asyncio
async def test_a_backfilled_scan_fact_never_beats_a_fact_said_since(db_session):
    """The history scan writes a fact now from an old line; it only fills gaps. Backfilled,
    it is written later but quotes an older message: unclear, so both stay."""
    from app.models.orm import Chat, Message

    user = await _make_user(db_session)
    chat = Chat(user_id=user.id, title="Old chat")
    db_session.add(chat)
    await db_session.flush()
    line = Message(chat_id=chat.id, user_id=user.id, role="user", content="I live in Denver")
    line.created_at = _JAN
    db_session.add(line)
    await db_session.flush()
    said_since = _denver(user.id, "User is based in Denver", written=_FEB)
    scanned = _denver(
        user.id, "User lives in Denver", written=_MAR, created=_MAR, source_message_id=line.id
    )
    db_session.add_all([said_since, scanned])
    await db_session.flush()

    retired = await memories_repo.retire_near_duplicates(
        db_session, user.id, [scanned.id], min_similarity=0.9, by_age=True
    )

    assert retired == 0
    assert (said_since.status, scanned.status) == ("active", "active")


@pytest.mark.asyncio
async def test_writes_and_the_turns_scoring_read_only_the_rows_they_use(db_session):
    """A superseded row is history: a write loaded every one, forever. A muted row never
    reaches a prompt: the turn's semantic read scored it, then threw it away (audit,
    2026-11-25). A write still reads a muted row: an add of its text keeps it muted."""
    from app.modules.memory.writes_repository import MemoryFactWrite, apply_fact_ops

    user = await _make_user(db_session)
    rows = {
        status: Memory(
            user_id=user.id,
            type="fact",
            text=f"User keeps a {status} note",
            status=status,
            embedding=[0.1] * 1536,
        )
        for status in ("active", "muted", "superseded")
    }
    db_session.add_all(rows.values())
    await db_session.flush()
    ids = {status: row.id for status, row in rows.items()}
    db_session.expunge_all()

    statements = []
    execute = db_session.execute

    async def _recorded(statement, *args, **kwargs):
        statements.append(statement)
        return await execute(statement, *args, **kwargs)

    with patch.object(db_session, "execute", _recorded):
        await apply_fact_ops(
            db_session,
            user.id,
            [
                MemoryFactWrite(
                    op="add", type="fact", text="User keeps a muted note", confidence=0.9
                )
            ],
            None,
            active_cap=150,
        )
    # The facts the write read: its first statement, run again.
    loaded = {row.id for row in (await execute(statements[0])).scalars().all()}
    assert ids["superseded"] not in loaded
    assert {ids["active"], ids["muted"]} <= loaded
    muted = await db_session.get(Memory, ids["muted"])
    assert muted is not None and muted.status == "muted"

    scored = await memories_repo.list_scored_for_user(db_session, user.id, [0.1] * 1536)
    assert [memory.id for memory, _score in scored] == [ids["active"]]
