"""Memory management regressions using local SQL and mocked external services."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.orm import Memory
from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult
from app.services import memory as memory_service
from app.services.memory import extraction_workflow
from app.services.memory.apply import apply_memory_section_rows
from app.services.memory.text import embedding_text_hash


@pytest.fixture
def memory_session():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE users (id UUID PRIMARY KEY, memory_enabled BOOLEAN NOT NULL)"
        )
    Memory.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as sync_session:
        session = AsyncMock(spec=AsyncSession)
        session.execute.side_effect = sync_session.execute
        session.commit.side_effect = sync_session.commit
        session.rollback.side_effect = sync_session.rollback
        session.refresh.side_effect = sync_session.refresh
        session.flush.side_effect = sync_session.flush
        session.get.side_effect = sync_session.get

        async def enter():
            sync_session.expire_all()
            return session

        session.__aenter__.side_effect = enter
        yield sync_session, session
    engine.dispose()


@pytest.fixture
def memory_services():
    with (
        patch.object(
            memory_service, "_acquire_memory_write_lock_or_raise", AsyncMock(return_value="lease")
        ),
        patch.object(memory_service, "release_memory_write_lock", AsyncMock()),
        patch.object(memory_service, "invalidate_memory_block", AsyncMock()) as invalidate_memory,
        patch("app.services.home.invalidate_home_cache", AsyncMock()) as invalidate_home,
    ):
        yield invalidate_memory, invalidate_home


def _memory(sync_session):
    row = Memory(
        user_id=uuid4(),
        type="fact",
        text="Owns a bicycle. Likes hiking.",
        embedding=[0.1] * 1536,
        embedding_json="[0.1]",
        embedding_text_hash="old-hash",
    )
    sync_session.add(row)
    sync_session.execute(
        text("INSERT INTO users (id, memory_enabled) VALUES (:id, true)"), {"id": row.user_id.hex}
    )
    sync_session.commit()
    return row


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["edit", "delete_fact"])
@pytest.mark.parametrize("failure", [None, RuntimeError("embedding unavailable")])
async def test_memory_text_change_discards_stale_embeddings(
    memory_session, memory_services, operation, failure
):
    sync_session, session = memory_session
    row = _memory(sync_session)
    embed = AsyncMock(return_value=None, side_effect=failure)
    with patch("app.gateways.embedding_gateway.embed_text", embed):
        if operation == "edit":
            await memory_service.update_memory(
                session, Settings(), row.user_id, row.id, "Owns a scooter."
            )
        else:
            assert await memory_service.delete_memory_fact(
                session, Settings(), row.user_id, row.id, 0
            )

    sync_session.refresh(row)
    assert row.embedding is None
    assert row.embedding_json is None
    assert row.embedding_text_hash is None
    assert "bicycle" not in row.text


@pytest.mark.asyncio
async def test_fact_delete_stores_hash_for_its_new_embedding(memory_session, memory_services):
    sync_session, session = memory_session
    row = _memory(sync_session)
    with patch("app.gateways.embedding_gateway.embed_text", AsyncMock(return_value=[0.2] * 1536)):
        assert await memory_service.delete_memory_fact(session, Settings(), row.user_id, row.id, 0)

    sync_session.refresh(row)
    assert row.embedding_text_hash == embedding_text_hash(row.text)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["edit", "delete_fact", "delete_row", "delete_section"])
async def test_manual_memory_change_invalidates_home_after_commit(
    memory_session, memory_services, operation
):
    sync_session, session = memory_session
    row = _memory(sync_session)
    owner_id = row.user_id
    with patch("app.gateways.embedding_gateway.embed_text", AsyncMock(return_value=None)):
        if operation == "edit":
            await memory_service.update_memory(
                session, Settings(), owner_id, row.id, "Owns a scooter."
            )
        elif operation == "delete_fact":
            await memory_service.delete_memory_fact(session, Settings(), owner_id, row.id, 0)
        elif operation == "delete_row":
            await memory_service.delete_memory(session, owner_id, row.id)
        else:
            await memory_service.delete_memory_section(session, owner_id, row.type)

    _, invalidate_home = memory_services
    session.commit.assert_awaited_once()
    invalidate_home.assert_awaited_once_with(owner_id)


@pytest.mark.asyncio
async def test_memory_edit_rejects_a_date_stamp_without_facts(memory_session, memory_services):
    sync_session, session = memory_session
    row = _memory(sync_session)
    with patch("app.gateways.embedding_gateway.embed_text", AsyncMock(return_value=None)) as embed:
        with pytest.raises(memory_service.MemoryEmptyTextError):
            await memory_service.update_memory(
                session, Settings(), row.user_id, row.id, "As of 2026-09-04: "
            )

    embed.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("intervening_change", ["edit", "delete", "disable"])
async def test_extraction_cannot_restore_memory_after_manual_change(
    memory_session, memory_services, intervening_change
):
    sync_session, session = memory_session
    row = _memory(sync_session)
    owner_id, memory_id = row.user_id, row.id
    result = MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="fact",
                summary="Owns a bicycle. Likes hiking. Enjoys camping.",
                confidence=0.95,
            )
        ]
    )

    async def revise(*args, **kwargs):
        current = sync_session.get(Memory, memory_id)
        if intervening_change == "edit":
            current.text = "Manual replacement."
        elif intervening_change == "delete":
            sync_session.delete(current)
        else:
            sync_session.execute(
                text("UPDATE users SET memory_enabled = false WHERE id = :id"), {"id": owner_id.hex}
            )
        sync_session.commit()
        return result

    with (
        patch.object(extraction_workflow, "SessionLocal", return_value=session),
        patch.object(
            extraction_workflow,
            "acquire_memory_write_lock",
            AsyncMock(return_value="expired-lease"),
        ),
        patch.object(extraction_workflow, "release_memory_write_lock", AsyncMock()),
        patch.object(
            extraction_workflow.users_repo,
            "get_by_id",
            AsyncMock(return_value=SimpleNamespace(memory_enabled=True)),
        ),
        patch.object(
            extraction_workflow,
            "expand_memory_extract_transcript",
            AsyncMock(return_value=("I enjoy camping", None)),
        ),
        patch.object(
            extraction_workflow.memory_llm, "revise_memory_sections", AsyncMock(side_effect=revise)
        ),
        patch("app.gateways.embedding_gateway.embed_text", AsyncMock(return_value=None)),
    ):
        await extraction_workflow.extract_and_store_memories(
            Settings(), user_id=owner_id, chat_id=uuid4(), transcript="I enjoy camping"
        )

    sync_session.expire_all()
    persisted = sync_session.get(Memory, memory_id)
    if intervening_change == "delete":
        assert sync_session.query(Memory).filter_by(user_id=owner_id).all() == []
    elif intervening_change == "edit":
        assert persisted.text == "Manual replacement."
    else:
        assert persisted.text == "Owns a bicycle. Likes hiking."


@pytest.mark.asyncio
async def test_late_background_embedding_cannot_replace_manual_edit_vector(
    memory_session, memory_services
):
    sync_session, session = memory_session
    row = _memory(sync_session)
    owner_id, memory_id = row.user_id, row.id

    async def embed(*args):
        current = sync_session.get(Memory, memory_id)
        current.text = "Manual replacement."
        current.embedding = None
        current.embedding_json = None
        current.embedding_text_hash = None
        sync_session.commit()
        return [0.3] * 1536

    with patch("app.gateways.embedding_gateway.embed_text", AsyncMock(side_effect=embed)):
        await apply_memory_section_rows(
            Settings(),
            user_id=owner_id,
            rows=[("fact", "Generated text.", 0.95, None)],
            session_factory=lambda: session,
        )

    sync_session.refresh(row)
    assert row.text == "Manual replacement."
    assert row.embedding is None
    assert row.embedding_text_hash is None
