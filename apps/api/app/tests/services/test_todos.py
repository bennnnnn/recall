from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.schemas import TodoActionItem
from app.repositories import todos as todos_repo
from app.repositories import users as users_repo
from app.services import home as home_service
from app.services import todos as todos_service
from app.services.todos import actions as todos_actions
from app.services.todos import classification as todos_classification


class _FakeSessionCM:
    def __init__(self, session: AsyncMock):
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _session_local_side_effect(session: AsyncMock):
    return [_FakeSessionCM(session), _FakeSessionCM(session)]


def _item(content: str, topic: str = "Groceries", checked: bool = False):
    item = MagicMock()
    item.id = uuid4()
    item.topic = topic
    item.content = content
    item.checked = checked
    item.due_at = None
    return item


def _item_due_today(content: str, *, hour: int = 9, tz_name: str = "UTC"):
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    due_local = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    item = _item(content)
    item.due_at = due_local.astimezone(UTC)
    return item


def _item_overdue(content: str, *, hours_ago: int = 3, tz_name: str = "UTC"):
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name)
    due_local = datetime.now(tz) - timedelta(hours=hours_ago)
    item = _item(content, topic="Reminders")
    item.due_at = due_local.astimezone(UTC)
    return item


def test_transcript_implies_bulk_shift_to_tomorrow():
    assert todos_classification._transcript_implies_bulk_shift_to_tomorrow(
        "User: move all my reminders due today to tomorrow\nAssistant: Done."
    )
    assert todos_classification._transcript_implies_bulk_shift_to_tomorrow(
        "User: you only moved one, fix them\nAssistant: Moving the rest now."
    )
    assert not todos_classification._transcript_implies_bulk_shift_to_tomorrow(
        "User: move Walk to tomorrow\nAssistant: Done."
    )


@pytest.mark.asyncio
async def test_apply_bulk_shift_moves_all_due_today():
    session = AsyncMock()
    items = [
        _item_due_today("Walk", hour=9),
        _item_due_today("Call mom", hour=14),
        _item("Buy milk"),
    ]
    with patch.object(
        todos_repo,
        "update",
        AsyncMock(side_effect=lambda _s, item, **fields: item),
    ) as update_mock:
        applied = await todos_actions._apply_bulk_shift_due_today_to_tomorrow(
            session,
            user_id=uuid4(),
            items=items,
            user_timezone="UTC",
        )
    assert applied == 2
    assert update_mock.await_count == 2


@pytest.mark.asyncio
async def test_sync_todos_bulk_shift_after_partial_llm_apply():
    session = AsyncMock()
    user_id = uuid4()
    user = MagicMock()
    user.timezone = "UTC"
    items = [_item_due_today("A"), _item_due_today("B"), _item_due_today("C")]
    extraction = MagicMock()
    extraction.actions = [
        TodoActionItem(
            action="set_due",
            topic="General",
            content="A",
            due_at=datetime.now(UTC) + timedelta(days=1),
        )
    ]

    with (
        patch(
            "app.core.db.SessionLocal",
            side_effect=_session_local_side_effect(session),
        ),
        patch.object(
            users_repo,
            "get_by_id",
            AsyncMock(return_value=user),
        ),
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=items),
        ),
        patch(
            "app.services.todos.extract.extract_todo_actions",
            AsyncMock(return_value=extraction),
        ),
        patch.object(
            todos_service,
            "apply_todo_actions",
            AsyncMock(return_value=1),
        ),
        patch.object(
            todos_actions,
            "_apply_bulk_shift_due_today_to_tomorrow",
            AsyncMock(return_value=2),
        ) as bulk_mock,
    ):
        await todos_service.sync_todos_from_transcript(
            Settings(),
            user_id=user_id,
            chat_id=uuid4(),
            transcript="User: move all reminders due today to tomorrow\nAssistant: Done.",
        )
    bulk_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_todos_from_transcript_releases_db_before_llm():
    session = AsyncMock()
    session.commit = AsyncMock()
    db_open_during_extract: list[bool] = []

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

    async def fake_extract(*_args: object, **_kwargs: object) -> None:
        db_open_during_extract.append(load_cm.open or apply_cm.open)
        return None

    with (
        patch("app.core.db.SessionLocal", side_effect=[load_cm, apply_cm]),
        patch.object(
            users_repo,
            "get_by_id",
            AsyncMock(return_value=MagicMock(timezone="UTC")),
        ),
        patch.object(todos_repo, "list_for_user", AsyncMock(return_value=[])),
        patch(
            "app.services.todos.extract.extract_todo_actions",
            AsyncMock(side_effect=fake_extract),
        ),
    ):
        await todos_service.sync_todos_from_transcript(
            Settings(),
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="User: add milk\nAssistant: ok",
        )

    assert db_open_during_extract == [False]
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_sync_todos_refuses_delete_list_from_transcript_and_caps_actions():
    """A delete_list inferred from a transcript must not be applied, and only the
    first MAX_TODO_ACTIONS_PER_TURN actions run."""
    session = AsyncMock()
    user_id = uuid4()
    user = MagicMock()
    user.timezone = "UTC"
    extraction = MagicMock()
    extraction.actions = [
        TodoActionItem(action="delete_list", topic="Work", content=""),
        *[
            TodoActionItem(action="add", topic="Shop", content=f"item-{i}")
            for i in range(todos_service.MAX_TODO_ACTIONS_PER_TURN + 3)
        ],
    ]

    captured: dict[str, object] = {}

    async def fake_apply(*args, **kwargs):
        captured["actions"] = kwargs.get("actions") or args[0]
        return len(captured["actions"])

    with (
        patch(
            "app.core.db.SessionLocal",
            side_effect=_session_local_side_effect(session),
        ),
        patch.object(users_repo, "get_by_id", AsyncMock(return_value=user)),
        patch.object(todos_repo, "list_for_user", AsyncMock(return_value=[])),
        patch(
            "app.services.todos.extract.extract_todo_actions",
            AsyncMock(return_value=extraction),
        ),
        patch.object(todos_service, "apply_todo_actions", AsyncMock(side_effect=fake_apply)),
        patch.object(
            todos_actions,
            "_apply_bulk_shift_due_today_to_tomorrow",
            AsyncMock(return_value=0),
        ),
    ):
        await todos_service.sync_todos_from_transcript(
            Settings(),
            user_id=user_id,
            chat_id=uuid4(),
            transcript="User: delete my work list and add milk eggs bread extra\nAssistant: ok",
        )

    sent = captured["actions"]
    assert all(a.action != "delete_list" for a in sent)
    assert len(sent) == todos_service.MAX_TODO_ACTIONS_PER_TURN


def test_format_todos_block_groups_by_topic():
    block = todos_service.format_todos_block(
        [
            _item("Milk", "Groceries"),
            _item("Report", "Work"),
            _item("Eggs", "Groceries", checked=True),
        ]
    )
    assert "User Lists" in block
    assert "User Reminders" not in block
    assert "## Groceries" in block
    assert "## Work" in block
    assert "○ Milk" in block
    assert "(open)" in block
    assert "✓ Eggs" in block
    assert "(done)" in block


def test_format_todos_block_splits_reminders_and_lists():
    due_item = _item("Reading at 10", "General")
    due_item.due_at = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    block = todos_service.format_todos_block(
        [
            due_item,
            _item("Milk", "Groceries"),
        ],
        user_timezone="UTC",
    )
    assert "User Reminders" in block
    assert "Reading at 10" in block
    assert "### " in block
    assert "User Lists" in block
    assert "## Groceries" in block
    assert block.index("User Reminders") < block.index("User Lists")


@pytest.mark.asyncio
async def test_apply_todo_actions_delete_list():
    session = AsyncMock()
    done_a = _item("Task A", "Work")
    done_a.checked = True
    done_b = _item("Task B", "Work")
    done_b.checked = True
    with (
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=[done_a, done_b]),
        ),
        patch.object(
            todos_repo,
            "delete_by_topic",
            AsyncMock(return_value=2),
        ) as delete_mock,
    ):
        applied = await todos_service.apply_todo_actions(
            session,
            user_id=uuid4(),
            actions=[TodoActionItem(action="delete_list", topic="Work", content="")],
        )
    assert applied == 1
    delete_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_todo_actions_delete_list_blocked_when_open():
    session = AsyncMock()
    items = [_item("Task A", "Work")]
    feedback: list[str] = []
    with patch.object(
        todos_repo,
        "list_for_user",
        AsyncMock(return_value=items),
    ):
        applied = await todos_service.apply_todo_actions(
            session,
            user_id=uuid4(),
            actions=[TodoActionItem(action="delete_list", topic="Work", content="")],
            feedback=feedback,
        )
    assert applied == 0
    assert any("Blocked delete list" in line for line in feedback)


@pytest.mark.asyncio
async def test_apply_todo_actions_complete():
    session = AsyncMock()
    existing = _item("Buy milk", "Groceries")
    with (
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            todos_repo,
            "update",
            AsyncMock(return_value=existing),
        ) as update_mock,
    ):
        applied = await todos_service.apply_todo_actions(
            session,
            user_id=uuid4(),
            actions=[
                TodoActionItem(action="complete", topic="Groceries", content="Buy milk"),
            ],
        )
    assert applied == 1
    update_mock.assert_awaited()


@pytest.mark.asyncio
async def test_apply_todo_actions_set_due():
    session = AsyncMock()
    existing = _item("Pay rent", "Home")
    due = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    with (
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            todos_repo,
            "update",
            AsyncMock(return_value=existing),
        ) as update_mock,
    ):
        applied = await todos_service.apply_todo_actions(
            session,
            user_id=uuid4(),
            actions=[
                TodoActionItem(
                    action="set_due",
                    topic="Home",
                    content="Pay rent",
                    due_at=due,
                )
            ],
            user_timezone="UTC",
        )
    assert applied == 1
    update_mock.assert_awaited()


@pytest.mark.asyncio
async def test_load_todos_for_prompt():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    with patch.object(
        todos_repo,
        "list_for_user",
        AsyncMock(return_value=[_item("Task")]),
    ):
        block = await todos_service.load_todos_for_prompt(
            session, user, Settings(), query_text="Show my tasks"
        )
    assert "Task" in block


def test_select_todos_for_prompt_prioritizes_overdue():
    now = datetime.now(UTC)
    overdue = _item("Overdue task")
    overdue.due_at = now - timedelta(days=1)
    future = _item("Later task")
    future.due_at = now + timedelta(days=30)
    filler = [_item(f"Filler {i}") for i in range(50)]
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


def test_query_implies_todos():
    assert todos_service.query_implies_todos("What's on my todo list?")
    assert todos_service.query_implies_todos("Add milk to my grocery list")
    assert not todos_service.query_implies_todos("Who am I?")
    assert not todos_service.query_implies_todos("Explain quantum physics")


def test_fuzzy_match_requires_similarity_not_substring():
    from app.services.todos.actions import _fuzzy_match

    assert not _fuzzy_match("milk", "buy milk today")
    assert not _fuzzy_match("call mom", "call mom about dinner and groceries")
    assert _fuzzy_match("buy organic milk", "buy organic milke")


def test_todo_hint_does_not_promise_pre_reply_application():
    """The todo sync runs as a post-reply background job, so the prompt must
    not tell the model changes apply 'before your reply' (it would then phrase
    completed actions as already done, which is misleading). Guard against
    regressing back to the old pre-reply copy."""
    hint = todos_service.TODO_HINT
    assert "before your reply" not in hint
    assert "pre-reply sync" not in hint
    # The honest phrasing must be present.
    assert "right after" in hint
    # Whole-list delete is blocked from chat — the prompt must say so.
    assert "whole-list delete is NOT supported from chat" in hint


def test_todo_sync_feedback_header_describes_post_reply_timing():
    header = todos_service.TODO_SYNC_FEEDBACK_HEADER
    assert "before this reply" not in header
    assert "after the previous reply" in header


def test_transcript_implies_todo_sync():
    assert todos_service.transcript_implies_todo_sync(
        "User: add eggs\nAssistant: Added eggs to Groceries."
    )
    assert todos_service.transcript_implies_todo_sync(
        "User: move all reminders due today to tomorrow\nAssistant: Done."
    )
    assert not todos_service.transcript_implies_todo_sync("User: hello\nAssistant: Hi there!")


def test_transcript_implies_todo_sync_overdue_delete():
    """Bare 'Delete' + future-tense claim must enqueue the todos job."""
    assert todos_service.transcript_implies_todo_sync(
        "User: Delete\nAssistant: I'll delete the 'Prosecutor's Soccer Clinic' reminder now."
    )
    assert todos_service.transcript_implies_todo_sync(
        "User: delete it\nAssistant: I'll delete that reminder now."
    )
    assert todos_service.transcript_implies_todo_sync(
        "User: yes\nAssistant: I deleted Pay rent from your reminders."
    )
    assert todos_service.transcript_implies_todo_sync(
        "User: Delete overdue\nAssistant: I've removed the two overdue reminders."
    )
    assert todos_classification._transcript_implies_delete_overdue(
        "User: Delete overdue\nAssistant: Done."
    )
    assert todos_classification._transcript_implies_delete_overdue(
        "User: yes\nAssistant: I've removed the two overdue reminders: Dd and midnight check."
    )
    # Unrelated chat must not fire a todo sync LLM call.
    assert not todos_service.transcript_implies_todo_sync(
        "User: how do I delete a file in Python?\nAssistant: Use os.remove."
    )
    assert not todos_classification._transcript_implies_delete_overdue(
        "User: delete the Walk reminder\nAssistant: I'll delete Walk."
    )


@pytest.mark.asyncio
async def test_apply_delete_overdue_removes_past_due_only():
    session = AsyncMock()
    overdue = _item_overdue("Dd — midnight check", hours_ago=12)
    future = _item("World Cup", topic="Reminders")
    future.due_at = datetime.now(UTC) + timedelta(days=7)
    no_due = _item("Milk")
    checked = _item_overdue("Done already", hours_ago=5)
    checked.checked = True
    with patch.object(
        todos_repo,
        "delete_by_id",
        AsyncMock(return_value=True),
    ) as delete_mock:
        applied = await todos_actions._apply_delete_overdue_open_reminders(
            session,
            user_id=uuid4(),
            items=[overdue, future, no_due, checked],
            user_timezone="UTC",
        )
    assert applied == 1
    delete_mock.assert_awaited_once()
    assert delete_mock.await_args.args[1] == overdue.id


@pytest.mark.asyncio
async def test_sync_todos_does_not_bulk_wipe_overdue_after_empty_llm_apply():
    """Transcript sync must not mass-delete overdue items via heuristic wipe."""
    session = AsyncMock()
    user_id = uuid4()
    user = MagicMock()
    user.timezone = "UTC"
    items = [_item_overdue("Dd"), _item_overdue("midnight check")]
    extraction = MagicMock()
    extraction.actions = []

    with (
        patch(
            "app.core.db.SessionLocal",
            side_effect=_session_local_side_effect(session),
        ),
        patch.object(
            users_repo,
            "get_by_id",
            AsyncMock(return_value=user),
        ),
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=items),
        ),
        patch(
            "app.services.todos.extract.extract_todo_actions",
            AsyncMock(return_value=extraction),
        ),
        patch.object(
            todos_service,
            "apply_todo_actions",
            AsyncMock(return_value=0),
        ),
        patch.object(
            todos_actions,
            "_apply_delete_overdue_open_reminders",
            AsyncMock(return_value=2),
        ) as delete_mock,
        patch.object(
            home_service,
            "invalidate_home_cache",
            AsyncMock(),
        ),
    ):
        await todos_service.sync_todos_from_transcript(
            Settings(),
            user_id=user_id,
            chat_id=uuid4(),
            transcript=("User: Delete overdue\nAssistant: I've removed the two overdue reminders."),
        )
    delete_mock.assert_not_awaited()


def test_transcript_implies_todo_sync_reminder_confirm():
    """Past-tense / emoji confirms and Yes+reminder must enqueue sync."""
    assert todos_service.transcript_implies_todo_sync(
        "User: Yes\nAssistant: ✅ Reminder set!\n\n**2026 FIFA World Cup Final**"
    )
    assert todos_service.transcript_implies_todo_sync(
        "User: sure\nAssistant: I've set a reminder for the match on Sunday."
    )
    assert todos_service.transcript_implies_todo_sync(
        "User: yes\nAssistant: I'll set a reminder for July 19 at 3 PM ET."
    )
    assert not todos_service.transcript_implies_todo_sync(
        "User: yes\nAssistant: Sounds good — anything else?"
    )


@pytest.mark.asyncio
async def test_apply_todo_actions_reminder_without_topic():
    """Dated reminder adds work even when the extractor omits a list title."""
    session = AsyncMock()
    due = datetime(2026, 7, 19, 19, 0, tzinfo=UTC)
    with (
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            todos_repo,
            "create",
            AsyncMock(),
        ) as create_mock,
    ):
        applied = await todos_service.apply_todo_actions(
            session,
            user_id=uuid4(),
            actions=[
                TodoActionItem(
                    action="add",
                    topic="",
                    content="2026 FIFA World Cup Final – Watch the match",
                    due_at=due,
                ),
            ],
            user_timezone="America/New_York",
        )
    assert applied == 1
    create_mock.assert_awaited_once()
    kwargs = create_mock.await_args.kwargs
    assert kwargs["topic"] == todos_service.REMINDER_TOPIC
    assert kwargs["due_at"] is not None


@pytest.mark.asyncio
async def test_materialize_reminder_fences_creates_todo():
    session = AsyncMock()
    due = datetime(2026, 7, 19, 19, 0, tzinfo=UTC)
    text = (
        "✅ Reminder set!\n\n"
        "```reminder\n"
        '{"title":"2026 FIFA World Cup Final","due_at":"2026-07-19T15:00:00-04:00"}\n'
        "```\n"
    )
    with (
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            todos_repo,
            "create",
            AsyncMock(),
        ) as create_mock,
        patch.object(
            home_service,
            "invalidate_home_cache",
            AsyncMock(),
        ) as invalidate_mock,
    ):
        updated, created = await todos_service.materialize_reminder_fences(
            session,
            user_id=uuid4(),
            chat_id=uuid4(),
            assistant_text=text,
            user_timezone="America/New_York",
        )
    assert created == 1
    assert "```reminder" not in updated
    assert "Reminder set" in updated
    create_mock.assert_awaited_once()
    kwargs = create_mock.await_args.kwargs
    assert kwargs["topic"] == todos_service.REMINDER_TOPIC
    assert kwargs["content"] == "2026 FIFA World Cup Final"
    assert kwargs["due_at"] is not None
    assert kwargs["due_at"].tzinfo is not None
    # 3pm ET → 19:00 UTC
    assert kwargs["due_at"].hour == due.hour
    invalidate_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_materialize_reminder_fences_skips_invalid():
    session = AsyncMock()
    text = 'Hello\n```reminder\n{"title":"x"}\n```\n'
    with patch.object(todos_repo, "create", AsyncMock()) as create_mock:
        updated, created = await todos_service.materialize_reminder_fences(
            session,
            user_id=uuid4(),
            chat_id=uuid4(),
            assistant_text=text,
            user_timezone="UTC",
        )
    assert created == 0
    assert "```reminder" in updated
    create_mock.assert_not_awaited()


def test_todo_hint_covers_reminder_confirm_timing():
    hint = todos_service.TODO_HINT
    assert "```reminder" in hint
    assert "Only say a reminder is set if you emitted that fence" in hint


def test_should_inject_todos_prompt():
    overdue = _item("Late task")
    overdue.due_at = datetime.now(UTC) - timedelta(days=1)
    assert todos_service.should_inject_todos_prompt(
        [overdue], query_text="Tell me a joke", user_timezone="UTC"
    )
    assert not todos_service.should_inject_todos_prompt(
        [_item("Milk")], query_text="Tell me a joke", user_timezone="UTC"
    )
    assert todos_service.should_inject_todos_prompt(
        [_item("Milk")], query_text="Show my grocery list", user_timezone="UTC"
    )
    assert todos_service.should_inject_todos_prompt(
        [_item("Milk")],
        query_text="How's my day looking so far — anything you think I should prioritize?",
        user_timezone="UTC",
    )


@pytest.mark.asyncio
async def test_apply_todo_actions_dedupes_add():
    session = AsyncMock()
    existing = _item("Buy milk", "Groceries")
    with (
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            todos_repo,
            "create",
            AsyncMock(),
        ) as create_mock,
    ):
        applied = await todos_service.apply_todo_actions(
            session,
            user_id=uuid4(),
            actions=[
                TodoActionItem(action="add", topic="Groceries", content="Buy milk"),
            ],
        )
    assert applied == 0
    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_todo_actions_wildcard_set_due_today():
    session = AsyncMock()
    due_today_a = _item_due_today("Walk", hour=9)
    due_today_b = _item_due_today("Call", hour=14)
    list_item = _item("Milk")
    new_due = datetime.now(UTC) + timedelta(days=1)
    with (
        patch.object(
            todos_repo,
            "list_for_user",
            AsyncMock(return_value=[due_today_a, due_today_b, list_item]),
        ),
        patch.object(
            todos_repo,
            "update",
            AsyncMock(side_effect=lambda _s, item, **fields: item),
        ) as update_mock,
    ):
        applied = await todos_service.apply_todo_actions(
            session,
            user_id=uuid4(),
            actions=[
                TodoActionItem(
                    action="set_due",
                    topic="General",
                    content="*",
                    due_at=new_due,
                )
            ],
            user_timezone="UTC",
        )
    assert applied == 2
    assert update_mock.await_count == 2


@pytest.mark.asyncio
async def test_load_todos_for_prompt_skips_unrelated_query():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    with patch.object(
        todos_repo,
        "list_for_user",
        AsyncMock(return_value=[_item("Task")]),
    ):
        block = await todos_service.load_todos_for_prompt(
            session, user, Settings(), query_text="Who am I?"
        )
    assert block == ""


@pytest.mark.asyncio
async def test_build_todos_system_section_returns_hint_and_block():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    with patch.object(
        todos_repo,
        "list_for_user",
        AsyncMock(return_value=[_item("Task")]),
    ):
        section = await todos_service.build_todos_system_section(
            session, user, Settings(), query_text="Show my tasks"
        )
    assert section is not None
    assert "Recall has two features" in section
    assert "two todo features" not in section
    assert "Never call these features todos or tasks" in section
    assert "Task" in section
