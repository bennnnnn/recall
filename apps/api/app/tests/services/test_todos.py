from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.schemas import TodoActionItem
from app.services import todos as todos_service


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


def test_transcript_implies_bulk_shift_to_tomorrow():
    assert todos_service._transcript_implies_bulk_shift_to_tomorrow(
        "User: move all my reminders due today to tomorrow\nAssistant: Done."
    )
    assert todos_service._transcript_implies_bulk_shift_to_tomorrow(
        "User: you only moved one, fix them\nAssistant: Moving the rest now."
    )
    assert not todos_service._transcript_implies_bulk_shift_to_tomorrow(
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
        todos_service.todos_repo,
        "update",
        AsyncMock(side_effect=lambda _s, item, **fields: item),
    ) as update_mock:
        applied = await todos_service._apply_bulk_shift_due_today_to_tomorrow(
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
        patch.object(
            todos_service.users_repo,
            "get_by_id",
            AsyncMock(return_value=user),
        ),
        patch.object(
            todos_service.todos_repo,
            "list_for_user",
            AsyncMock(return_value=items),
        ),
        patch(
            "app.gateways.litellm_gateway.extract_todo_actions",
            AsyncMock(return_value=extraction),
        ),
        patch.object(
            todos_service,
            "apply_todo_actions",
            AsyncMock(return_value=1),
        ),
        patch.object(
            todos_service,
            "_apply_bulk_shift_due_today_to_tomorrow",
            AsyncMock(return_value=2),
        ) as bulk_mock,
    ):
        await todos_service.sync_todos_from_transcript(
            session,
            Settings(),
            user_id=user_id,
            chat_id=uuid4(),
            transcript="User: move all reminders due today to tomorrow\nAssistant: Done.",
        )
    bulk_mock.assert_awaited_once()


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
    items = [_item("Task A", "Work"), _item("Task B", "Work")]
    with (
        patch.object(
            todos_service.todos_repo,
            "list_for_user",
            AsyncMock(return_value=items),
        ),
        patch.object(
            todos_service.todos_repo,
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
async def test_apply_todo_actions_complete():
    session = AsyncMock()
    existing = _item("Buy milk", "Groceries")
    with (
        patch.object(
            todos_service.todos_repo,
            "list_for_user",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            todos_service.todos_repo,
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
            todos_service.todos_repo,
            "list_for_user",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            todos_service.todos_repo,
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
        todos_service.todos_repo,
        "list_for_user",
        AsyncMock(return_value=[_item("Task")]),
    ):
        block = await todos_service.load_todos_for_prompt(session, user, Settings())
    assert "Task" in block
