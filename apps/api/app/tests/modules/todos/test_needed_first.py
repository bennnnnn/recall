"""A turn's to-do read keeps the rows it needs, not the first ones in list order.

The prompt snapshot (100) and a chat's edits (500) read a limited list. Cut in list
order (topic, then the user's order), an overdue reminder whose topic sorts late fell
off behind finished to-dos, so the prompt never saw it and "done with Zumba" found
nothing to complete.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.modules.todos import actions as todo_actions
from app.modules.todos import repository as todos_repo
from app.modules.todos.schemas import TodoActionItem
from app.repositories import users as users_repo


async def _user_with_a_late_topic(session):
    """Four finished to-dos in topic "Aa", an undated open one and an overdue one in "Zz"."""
    user = await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    for index in range(4):
        done = await todos_repo.create(
            session, user_id=user.id, content=f"Old chore {index}", topic="Aa"
        )
        await todos_repo.update(session, done, checked=True)
    await todos_repo.create(session, user_id=user.id, content="Someday", topic="Zz")
    overdue = await todos_repo.create(
        session,
        user_id=user.id,
        content="Zumba class",
        topic="Zz",
        due_at=datetime.now(UTC) - timedelta(hours=3),
    )
    return user, overdue


@pytest.mark.asyncio
async def test_a_limited_read_keeps_the_open_and_overdue_first(db_session):
    user, overdue = await _user_with_a_late_topic(db_session)

    in_list_order = await todos_repo.list_for_user(db_session, user.id, limit=2)
    needed = await todos_repo.list_for_user(db_session, user.id, limit=2, needed_first=True)

    assert overdue.id not in {item.id for item in in_list_order}
    assert {item.content for item in needed} == {"Someday", "Zumba class"}
    # Need picks the rows, not their order: the overdue one outranks the undated one.
    only = await todos_repo.list_for_user(db_session, user.id, limit=1, needed_first=True)
    assert [item.id for item in only] == [overdue.id]


@pytest.mark.asyncio
async def test_a_chat_edit_finds_a_to_do_past_the_list_order_cut(db_session):
    user, overdue = await _user_with_a_late_topic(db_session)

    with patch.object(todo_actions, "ACTION_RELOAD_LIMIT", 2):
        applied = await todo_actions.apply_todo_actions(
            db_session,
            user_id=user.id,
            actions=[TodoActionItem(action="complete", topic="Zz", content="Zumba class")],
        )

    assert applied == 1
    await db_session.refresh(overdue)
    assert overdue.checked is True
