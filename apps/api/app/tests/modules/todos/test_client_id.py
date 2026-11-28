"""A to-do create named by the phone's id adds one row however often it is sent.

Pre-launch review, 2026-11-27: Save sent no id of its own, so a create whose answer was
lost and Save tapped again made a second to-do (migration 0138).
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import TodoItem
from app.modules.todos import api as todos_router
from app.modules.todos import crud as todos_crud
from app.repositories import users as users_repo


async def _user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


def _client(session, user) -> AsyncClient:
    app = FastAPI()
    app.include_router(todos_router.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _count(session, user_id) -> int:
    result = await session.execute(
        select(func.count()).select_from(TodoItem).where(TodoItem.user_id == user_id)
    )
    return int(result.scalar_one())


@pytest.mark.asyncio
@pytest.mark.parametrize("due_at", [None, "2026-12-01T15:00:00Z"])
async def test_create_sent_again_under_its_client_id_returns_the_same_todo(db_session, due_at):
    user = await _user(db_session)
    client_id = str(uuid4())
    body = {"content": "Buy milk", "client_id": client_id, **({"due_at": due_at} if due_at else {})}
    async with _client(db_session, user) as client:
        first = await client.post("/todos", json=body)
        again = await client.post("/todos", json=body)
    assert first.status_code == 201
    assert again.status_code == 201
    assert again.json()["id"] == first.json()["id"]
    assert await _count(db_session, user.id) == 1


@pytest.mark.asyncio
async def test_creates_without_or_with_other_client_ids_each_add_a_todo(db_session):
    user = await _user(db_session)
    async with _client(db_session, user) as client:
        for body in (
            {"content": "Buy milk"},
            {"content": "Buy milk"},
            {"content": "Buy milk", "client_id": str(uuid4())},
            {"content": "Buy milk", "client_id": str(uuid4())},
        ):
            assert (await client.post("/todos", json=body)).status_code == 201
    assert await _count(db_session, user.id) == 4


@pytest.mark.asyncio
async def test_client_id_is_per_account(db_session):
    """Another account's create under the same id is its own to-do, and shows nothing of the first."""
    first_user, other_user = await _user(db_session), await _user(db_session)
    client_id = uuid4()
    mine = await todos_crud.create_todo(
        db_session, first_user, content="Mine", topic=None, chat_id=None, due_at=None,
        client_id=client_id,
    )
    theirs = await todos_crud.create_todo(
        db_session, other_user, content="Theirs", topic=None, chat_id=None, due_at=None,
        client_id=client_id,
    )
    assert theirs.id != mine.id
    assert theirs.content == "Theirs"
    assert theirs.user_id == other_user.id


@pytest.mark.asyncio
async def test_a_create_racing_its_twin_returns_the_row_the_twin_made(db_session, monkeypatch):
    """Both sends passed the lookup before either inserted: the unique answers the second."""
    user = await _user(db_session)
    client_id = uuid4()
    made = await todos_crud.create_todo(
        db_session, user, content="Buy milk", topic=None, chat_id=None, due_at=None,
        client_id=client_id,
    )
    # The rollback below expires the rows the session holds.
    made_id, user_id = made.id, user.id
    looked_up = 0
    real_lookup = todos_crud.todos_repo.get_by_client_id

    async def miss_first(session, user_id, cid):
        nonlocal looked_up
        looked_up += 1
        return None if looked_up == 1 else await real_lookup(session, user_id, cid)

    monkeypatch.setattr(todos_crud.todos_repo, "get_by_client_id", miss_first)
    again = await todos_crud.create_todo(
        db_session, user, content="Buy milk", topic=None, chat_id=None, due_at=None,
        client_id=client_id,
    )
    assert again.id == made_id
    assert await _count(db_session, user_id) == 1
