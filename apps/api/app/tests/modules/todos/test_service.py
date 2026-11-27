from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.config import Settings
from app.modules import todos as todos_service
from app.modules.todos import crud as todos_crud
from app.modules.todos import repository as todos_repo
from app.modules.todos.prompt_context import format_todos_block, should_inject_todos_prompt
from app.modules.todos.prompt_hint import TODO_HINT
from app.modules.todos.schemas import TodoCreate, TodoUpdate
from app.tests.fakes import FakeSessionCM, fake_session


def _session_local_side_effect(session: AsyncMock):
    return [FakeSessionCM(session), FakeSessionCM(session)]


@asynccontextmanager
async def _nested_savepoint():
    yield


def _session_with_savepoint() -> AsyncMock:
    """AsyncMock session whose begin_nested() is sync, like SQLAlchemy's."""
    session = fake_session()
    session.begin_nested = MagicMock(side_effect=_nested_savepoint)
    return session


def test_todo_create_accepts_plain_undated_item():
    body = TodoCreate(content="Call mom")
    assert body.due_at is None
    assert body.recurrence_rule is None


def test_todo_schemas_have_no_project_id():
    assert "project_id" not in TodoCreate.model_fields
    assert "project_id" not in TodoUpdate.model_fields
    created = TodoCreate.model_validate({"content": "Call mom", "project_id": str(uuid4())})
    assert "project_id" not in created.model_dump()
    updated = TodoUpdate.model_validate({"project_id": str(uuid4())})
    assert updated.model_dump(exclude_unset=True) == {}


def test_todo_update_accepts_cleared_due_at():
    body = TodoUpdate(due_at=None)
    assert body.model_dump(exclude_unset=True) == {"due_at": None}


@pytest.mark.asyncio
async def test_update_todo_clears_due_at_and_recurrence():
    session = fake_session()
    user = MagicMock()
    user.id = uuid4()
    item = MagicMock()
    item.due_at = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    item.recurrence_rule = "weekly"
    updated = MagicMock()
    with (
        patch.object(todos_crud.todos_repo, "get_by_id", AsyncMock(return_value=item)),
        patch.object(todos_crud.todos_repo, "update", AsyncMock(return_value=updated)) as update,
    ):
        result = await todos_crud.update_todo(session, user, uuid4(), {"due_at": None})
    assert result is updated
    # An undated row keeps its flag true: only a date can be a date alone.
    update.assert_awaited_once_with(
        session, item, due_at=None, recurrence_rule=None, due_has_time=True
    )


@pytest.mark.asyncio
async def test_update_todo_rejects_recurrence_without_due():
    session = fake_session()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    item = MagicMock()
    item.due_at = None
    item.recurrence_rule = None
    with patch.object(todos_crud.todos_repo, "get_by_id", AsyncMock(return_value=item)):
        with pytest.raises(todos_crud.TodosError) as exc:
            await todos_crud.update_todo(session, user, uuid4(), {"recurrence_rule": "weekly"})
    assert exc.value.status_code == 422
    assert "due_at" in exc.value.detail


@pytest.mark.asyncio
async def test_create_todo_unique_violation_returns_existing():
    from sqlalchemy.exc import IntegrityError

    session = fake_session()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    due = datetime(2026, 9, 8, 15, tzinfo=UTC)
    existing = MagicMock()
    existing.id = uuid4()
    existing.content = "Call mom"
    existing.due_at = due
    with (
        patch.object(
            todos_crud.todos_repo,
            "create",
            AsyncMock(
                side_effect=IntegrityError("insert", {}, Exception("uq_todo_open_content_due"))
            ),
        ),
        patch.object(
            todos_crud.todos_repo,
            "get_open_dated_duplicate",
            AsyncMock(return_value=existing),
        ) as lookup,
    ):
        item = await todos_crud.create_todo(
            session,
            user,
            content="Call mom",
            topic="Reminders",
            chat_id=None,
            due_at=due,
        )
    assert item is existing
    lookup.assert_awaited_once()
    session.rollback.assert_awaited_once()


def test_is_open_content_due_conflict_reads_constraint_name():
    from sqlalchemy.exc import IntegrityError

    hit = IntegrityError("insert", {}, Exception("uq_todo_open_content_due"))
    other = IntegrityError("insert", {}, Exception("todo_items_pkey"))
    assert todos_repo.is_open_content_due_conflict(hit)
    assert not todos_repo.is_open_content_due_conflict(other)


def _item(content: str, topic: str = "Groceries", checked: bool = False):
    item = MagicMock()
    item.id = uuid4()
    item.topic = topic
    item.content = content
    item.checked = checked
    item.due_at = None
    item.source = "user"
    return item


def _item_due_today(content: str, *, hour: int = 9, tz_name: str = "UTC"):

    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    due_local = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    item = _item(content)
    item.due_at = due_local.astimezone(UTC)
    return item


def _item_overdue(content: str, *, hours_ago: int = 3, tz_name: str = "UTC"):

    tz = ZoneInfo(tz_name)
    due_local = datetime.now(tz) - timedelta(hours=hours_ago)
    item = _item(content, topic="Reminders")
    item.due_at = due_local.astimezone(UTC)
    return item


def test_format_todos_block_groups_undated_items_under_anytime():
    block = format_todos_block(
        [
            _item("Milk", "Groceries"),
            _item("Report", "Work"),
            _item("Eggs", "Groceries", checked=True),
        ]
    )
    assert "User To-do list" in block
    assert "### Anytime" in block
    assert "Milk" in block
    assert "Report" in block
    assert "### Completed" in block
    assert "Eggs" in block


def test_format_todos_block_includes_dated_and_plain_items():
    due_item = _item("Reading at 10", "General")
    due_item.due_at = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    block = format_todos_block(
        [
            due_item,
            _item("Milk", "Groceries"),
        ],
        user_timezone="UTC",
    )
    assert "User To-do list" in block
    assert "Reading at 10" in block
    assert "### " in block
    assert "User Lists" not in block
    assert "### Anytime" in block
    assert "Milk" in block


def test_format_todos_voice_block_is_plain_and_includes_undated():
    due_item = _item("Reading at 10", "General")
    due_item.due_at = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    block = todos_service.format_todos_voice_block(
        [due_item, _item("Milk", "Groceries")],
        user_timezone="UTC",
    )
    assert "User To-do list" in block
    assert "Reading at 10" in block
    assert "10:00" in block
    assert "### " not in block
    assert "Anytime: Milk" in block
    assert "Anytime: Milk" in todos_service.format_todos_voice_block([_item("Milk")])


def test_select_todos_for_prompt_prioritizes_overdue():
    now = datetime.now(UTC)
    overdue = _item("Overdue task")
    overdue.due_at = now - timedelta(days=1)
    future = _item("Later task")
    future.due_at = now + timedelta(days=30)
    filler = [_item(f"Filler {i}") for i in range(50)]
    for offset, item in enumerate(filler):
        item.due_at = now + timedelta(days=60 + offset)
    items = [*filler, future, overdue]
    selected = todos_service.select_todos_for_prompt(
        items,
        Settings(todo_prompt_limit=10),
        query_text=None,
        user_timezone="UTC",
    )
    assert overdue in selected
    assert len(selected) == 10
    assert selected.index(overdue) < selected.index(future)


def test_select_todos_for_prompt_keeps_matching_undated_item():
    """A relevant plain task must not be trimmed behind unrelated reminders."""
    now = datetime.now(UTC)
    grocery = _item("Buy groceries for dinner", "General")
    unrelated = [_item(f"Unrelated reminder {i}", "General") for i in range(8)]
    unrelated[0].content = "Show weekly report"
    for offset, item in enumerate(unrelated):
        item.due_at = now + timedelta(hours=offset + 1)

    selected = todos_service.select_todos_for_prompt(
        [*unrelated, grocery],
        Settings(todo_prompt_limit=8),
        query_text="show my grocery list",
        user_timezone="UTC",
    )

    assert grocery in selected
    assert selected[0] is grocery


def test_query_implies_todos():
    assert todos_service.query_implies_todos("What's on my todo list?")
    assert todos_service.query_implies_todos("mis recordatorios")
    assert todos_service.query_implies_todos("remind me to call mom tomorrow at 5pm")
    assert todos_service.query_implies_todos("Can you remind me")
    assert todos_service.query_implies_todos("Add milk to my grocery list")
    assert todos_service.query_implies_todos("mark laundry done")
    assert todos_service.query_implies_todos("move dentist to tomorrow")
    assert todos_service.query_implies_todos("What time is my flight")
    assert todos_service.query_implies_todos("when is the meeting")
    assert not todos_service.query_implies_todos("Who am I?")
    assert not todos_service.query_implies_todos("Explain quantum physics")
    assert not todos_service.query_implies_todos("tell me about flight delays")


@pytest.mark.parametrize(
    ("text", "loads"),
    [
        # The app's own name for the list, however it is spelled (live 2026-10-25).
        ("ok last thing, what's on my to do list right now?", True),
        ("hmm are you sure? check my to-do list again", True),
        ("add milk to my to-do list", True),
        ("put this on my to do list", True),
        ("my to-dos for the move", True),
        ("what do i have today", True),
        ("what do I have tomorrow?", True),
        ("things to do in lisbon", False),
        ("what to do today?", False),
        ("i have a lot to do this week", False),
        ("what do i have to do to get a visa?", False),
        ("how to do long division", False),
    ],
)
def test_query_implies_todos_reads_the_list_by_its_name(text: str, loads: bool) -> None:
    assert todos_service.query_implies_todos(text) is loads


def test_todo_hint_only_reads():
    """Chat reads to-dos and never writes them: the hint teaches no write fence, sends a
    change to To-do with the button, and never offers one (owner, 2026-11-27)."""
    hint = todos_service.TODO_HINT
    assert "```reminder" not in hint
    assert "```todo_link" in hint
    assert "You cannot add, change, complete or delete" in hint  # safety phrase
    assert "never offer to set a reminder" in hint  # safety phrase
    assert "do not ask" in hint and "flight number" in hint


def test_should_inject_todos_prompt():
    overdue = _item("Late task")
    overdue.due_at = datetime.now(UTC) - timedelta(days=1)
    assert should_inject_todos_prompt([overdue], query_text="Tell me a joke", user_timezone="UTC")
    assert not should_inject_todos_prompt(
        [_item("Milk")], query_text="Tell me a joke", user_timezone="UTC"
    )
    assert should_inject_todos_prompt(
        [_item("Milk")], query_text="Show my grocery list", user_timezone="UTC"
    )
    assert should_inject_todos_prompt(
        [_item("Milk")],
        query_text="How's my day looking so far — anything you think I should prioritize?",
        user_timezone="UTC",
    )


@pytest.mark.asyncio
async def test_list_todos_advances_past_due_daily():
    session = fake_session()
    past = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)
    now = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
    item = MagicMock()
    item.checked = False
    item.due_at = past
    item.recurrence_rule = "daily"
    item.notification_sent_at = now
    item.email_sent_at = now

    with patch.object(todos_crud, "advance_schedules_if_current", AsyncMock()) as advance:
        assert await todos_crud.advance_past_recurring(session, [item], timezone="UTC", now=now)

    advance.assert_awaited_once()
    snapshot, new_due = advance.await_args.args[1][0]
    assert snapshot.due_at == past
    assert new_due > now
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_todo_clears_sent_markers_when_due_changes():
    session = fake_session()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    item = MagicMock()
    item.due_at = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    item.recurrence_rule = None
    new_due = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)

    with (
        patch.object(todos_crud.todos_repo, "get_by_id", AsyncMock(return_value=item)),
    ):
        await todos_crud.update_todo(session, user, uuid4(), {"due_at": new_due})

    assert item.notification_sent_at is None
    assert item.email_sent_at is None


@pytest.mark.asyncio
async def test_build_todos_system_section_skips_unrelated_query():
    session = fake_session()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    list_mock = AsyncMock(return_value=[_item("Task")])
    with (
        patch.object(todos_repo, "list_due_soon", AsyncMock(return_value=[])),
        patch.object(todos_repo, "list_for_user", list_mock),
    ):
        section = await todos_service.build_todos_system_section(
            session, user, Settings(), query_text="Who am I?"
        )
    assert section is None
    list_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_todos_system_section_returns_hint_and_block():
    session = fake_session()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    dated = _item("Task")
    dated.due_at = datetime.now(UTC) + timedelta(hours=2)
    with (
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=[dated]),
        ),
    ):
        section = await todos_service.build_todos_system_section(
            session, user, Settings(), query_text="Show my tasks"
        )
    assert section is not None
    assert "To-do" in section
    assert "dates are optional" in section
    assert "two todo features" not in section
    assert TODO_HINT in section
    assert "Task" in section
