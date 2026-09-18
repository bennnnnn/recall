"""Real-Postgres tests for the Automations table: chat_id CASCADE and the
drawer chat-list exclusion filter (repositories/chats.py list_for_user).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.repositories import automations as automations_repo
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import users as users_repo


async def _user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


async def _automation(session, user_id, *, next_run_at=None):
    chat = await chats_repo.create(session, user_id=user_id, model="smart-chat")
    automation = await automations_repo.create(
        session,
        user_id=user_id,
        chat_id=chat.id,
        prompt="Find L3 backend jobs",
        frequency="daily",
        next_run_at=next_run_at or datetime.now(UTC) + timedelta(hours=1),
    )
    return automation, chat


@pytest.mark.asyncio
async def test_deleting_the_automation_chat_cascades_the_automation_row(db_session):
    user = await _user(db_session)
    automation, chat = await _automation(db_session, user.id)

    await chats_repo.delete_by_id(db_session, chat.id, user.id)

    again = await automations_repo.get_by_id(db_session, automation.id, user.id)
    assert again is None


@pytest.mark.asyncio
async def test_automation_chat_is_hidden_from_the_drawer_chat_list(db_session):
    user = await _user(db_session)
    automation, chat = await _automation(db_session, user.id)
    # An automation's dedicated chat still needs a message to pass the
    # existing has_messages filter — prove the automations exclusion is a
    # separate, additional condition, not a side effect of being empty.
    await messages_repo.create(
        db_session,
        chat_id=chat.id,
        user_id=user.id,
        role="user",
        content="Find L3 backend jobs",
    )
    ordinary_chat = await chats_repo.create(db_session, user_id=user.id, model="free-chat")
    await messages_repo.create(
        db_session,
        chat_id=ordinary_chat.id,
        user_id=user.id,
        role="user",
        content="hi",
    )

    listed = await chats_repo.list_for_user(db_session, user.id)

    listed_ids = {c.id for c in listed}
    assert ordinary_chat.id in listed_ids
    assert chat.id not in listed_ids
    assert automation.chat_id == chat.id


@pytest.mark.asyncio
async def test_list_due_only_returns_active_automations_at_or_before_cutoff(db_session):
    user = await _user(db_session)
    now = datetime.now(UTC)
    due, _ = await _automation(db_session, user.id, next_run_at=now - timedelta(minutes=1))
    not_due, _ = await _automation(db_session, user.id, next_run_at=now + timedelta(hours=1))
    paused, paused_chat = await _automation(
        db_session, user.id, next_run_at=now - timedelta(minutes=1)
    )
    await automations_repo.update(db_session, paused, status="paused")

    result = await automations_repo.list_due(db_session, cutoff=now)

    result_ids = {a.id for a in result}
    assert due.id in result_ids
    assert not_due.id not in result_ids
    assert paused.id not in result_ids
    assert paused_chat.id is not None  # keep the fixture referenced


@pytest.mark.asyncio
async def test_count_active_for_user_excludes_paused(db_session):
    user = await _user(db_session)
    active, _ = await _automation(db_session, user.id)
    paused, _ = await _automation(db_session, user.id)
    await automations_repo.update(db_session, paused, status="paused")

    count = await automations_repo.count_active_for_user(db_session, user.id)

    assert count == 1
    assert active.status == "active"
