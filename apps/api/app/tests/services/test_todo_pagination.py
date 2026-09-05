"""Schedule traversal regressions using real SQL without external services."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.types import DateTime, TypeDecorator

from app.models.orm import TodoItem
from app.routers import todos as todos_router
from app.services.todos import crud


class _UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


@pytest.fixture
def page_sql():
    columns = [c for c in TodoItem.__table__.c if isinstance(c.type, DateTime)]
    original_types = [c.type for c in columns]
    for column in columns:
        column.type = _UTCDateTime()
    engine = create_engine("sqlite://")
    TodoItem.__table__.create(engine)
    try:
        with Session(engine, expire_on_commit=False) as sync_session:
            session = AsyncMock(spec=AsyncSession)
            session.execute.side_effect = sync_session.execute
            session.commit.side_effect = sync_session.commit
            session.rollback.side_effect = sync_session.rollback
            user = SimpleNamespace(id=uuid4(), timezone="UTC", push_notifications_enabled=True)
            with patch("app.services.home.invalidate_home_cache", AsyncMock()) as invalidate:
                yield sync_session, session, user, invalidate
    finally:
        engine.dispose()
        for column, original_type in zip(columns, original_types, strict=True):
            column.type = original_type


def _seed(sync_session, owner, *, count=1001):
    timestamp = datetime(2026, 9, 4, tzinfo=UTC)
    rows = [
        TodoItem(
            id=UUID(f"abcdef00-0000-0000-0000-{index:012x}"),
            user_id=owner,
            content=f"Reminder {index}",
            topic="Reminders",
            sort_order=1,
            checked=False,
            due_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )
        for index in range(1, count + 1)
    ]
    sync_session.add_all(rows)
    sync_session.commit()
    return rows


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["checked", "sort_order", "topic"])
@pytest.mark.parametrize("direction", ["seen_later", "unseen_earlier"])
async def test_traversal_keeps_all_1001_rows_when_mutable_fields_cross_boundary(
    page_sql, field, direction
):
    sync_session, session, user, _ = page_sql
    rows = _seed(sync_session, user.id)
    if direction == "unseen_earlier" and field == "checked":
        for row in rows:
            row.checked = True
        sync_session.commit()
    first, cursor = await crud.list_todos_page(session, user)
    assert len(first) == 1000
    assert cursor is not None
    moving = rows[0] if direction == "seen_later" else rows[-1]
    later = {"checked": True, "sort_order": 2, "topic": "Z"}
    earlier = {"checked": False, "sort_order": 0, "topic": "A"}
    setattr(moving, field, (later if direction == "seen_later" else earlier)[field])
    sync_session.commit()
    second, cursor = await crud.list_todos_page(session, user, cursor=cursor)
    assert cursor is None
    assert [row.id for row in first + second] == [row.id for row in rows]


@pytest.mark.asyncio
async def test_equal_timestamps_and_foreign_cursor_remain_owner_scoped(page_sql):
    sync_session, session, user, _ = page_sql
    rows = _seed(sync_session, user.id, count=4)
    foreign_id = rows[1].id
    rows[1].user_id = uuid4()
    sync_session.commit()
    first, cursor = await crud.list_todos_page(session, user, limit=2)
    assert [row.id for row in first] == [rows[0].id, rows[2].id]
    assert cursor == rows[2].id
    second, cursor = await crud.list_todos_page(session, user, limit=2, cursor=cursor)
    assert [row.id for row in second] == [rows[3].id]
    assert cursor is None
    foreign_cursor_page, _ = await crud.list_todos_page(session, user, cursor=foreign_id)
    assert [row.id for row in foreign_cursor_page] == [rows[2].id, rows[3].id]


@pytest.mark.asyncio
async def test_deleted_cursor_and_seen_rows_do_not_skip_remaining_rows(page_sql):
    sync_session, session, user, _ = page_sql
    rows = _seed(sync_session, user.id, count=4)
    first, cursor = await crud.list_todos_page(session, user, limit=2)
    sync_session.execute(delete(TodoItem).where(TodoItem.id.in_([row.id for row in first])))
    sync_session.commit()
    second, next_cursor = await crud.list_todos_page(session, user, limit=2, cursor=cursor)
    assert [row.id for row in second] == [rows[2].id, rows[3].id]
    assert next_cursor is None  # An exact final page does not require an extra request.


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["delete", "owner"])
async def test_catchup_reloads_original_ids_and_keeps_empty_page_cursor(page_sql, change):
    sync_session, session, user, _ = page_sql
    rows = _seed(sync_session, user.id, count=3)
    user.push_notifications_enabled = False
    rows[0].recurrence_rule = "daily"
    rows[0].due_at = datetime.now(UTC) - timedelta(days=1)
    page_ids = [row.id for row in rows[:2]]
    sync_session.commit()
    advance = crud.advance_schedules_if_current

    async def change_selected_rows_then_advance(db, advances):
        statement = (
            delete(TodoItem) if change == "delete" else update(TodoItem).values(user_id=uuid4())
        )
        sync_session.execute(
            statement.where(TodoItem.id.in_(page_ids)).execution_options(synchronize_session=False)
        )
        # A mutable sort change must not pull the next row into the reload.
        rows[2].topic = "A"
        sync_session.commit()
        return await advance(db, advances)

    with patch.object(crud, "advance_schedules_if_current", change_selected_rows_then_advance):
        first, cursor = await crud.list_todos_page(session, user, limit=2)
    assert first == []
    assert cursor == page_ids[-1]
    second, next_cursor = await crud.list_todos_page(session, user, limit=2, cursor=cursor)
    assert [row.id for row in second] == [rows[2].id]
    assert next_cursor is None


@pytest.mark.asyncio
@pytest.mark.parametrize("push_enabled", [True, False])
async def test_page_keeps_existing_delivery_owner_policy(page_sql, push_enabled):
    sync_session, session, user, invalidate = page_sql
    row = _seed(sync_session, user.id, count=1)[0]
    due = datetime.now(UTC) - timedelta(days=2)
    row.due_at = due
    row.recurrence_rule = "daily"
    row.notification_sent_at = None
    user.push_notifications_enabled = push_enabled
    sync_session.commit()
    items, cursor = await crud.list_todos_page(session, user)
    assert cursor is None
    if push_enabled:
        assert items[0].due_at == due
        session.commit.assert_not_awaited()
        invalidate.assert_not_awaited()
    else:
        assert items[0].due_at > datetime.now(UTC)
        sync_session.refresh(row)
        assert items[0].due_at == row.due_at
        invalidate.assert_awaited_once_with(user.id)


@pytest.mark.asyncio
async def test_catchup_page_returns_concurrent_reschedule_without_overwriting_it(page_sql):
    sync_session, session, user, _ = page_sql
    row = _seed(sync_session, user.id, count=1)[0]
    row.due_at = datetime.now(UTC) - timedelta(days=2)
    row.recurrence_rule = "daily"
    user.push_notifications_enabled = False
    sync_session.commit()
    new_due = datetime.now(UTC) + timedelta(days=10)
    advance = crud.advance_schedules_if_current

    async def reschedule_then_advance(db, advances):
        sync_session.execute(
            update(TodoItem)
            .where(TodoItem.id == row.id)
            .values(due_at=new_due)
            .execution_options(synchronize_session=False)
        )
        sync_session.commit()
        return await advance(db, advances)

    with patch.object(crud, "advance_schedules_if_current", reschedule_then_advance):
        items, _ = await crud.list_todos_page(session, user)
    assert items[0].due_at == new_due


@pytest.fixture
async def page_client(page_sql):
    _, session, user, _ = page_sql
    app = FastAPI()
    app.include_router(todos_router.router)
    app.dependency_overrides[todos_router.get_current_user] = lambda: user
    app.dependency_overrides[todos_router.get_db] = lambda: session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_page_route_serializes_cursor_and_keeps_legacy_list(page_sql, page_client):
    sync_session, _, user, _ = page_sql
    rows = _seed(sync_session, user.id, count=3)
    response = await page_client.get("/todos/page", params={"limit": 2})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(row.id) for row in rows[:2]]
    cursor = response.json()["next_cursor"]
    assert cursor == str(rows[1].id)
    response = await page_client.get("/todos/page", params={"limit": 2, "cursor": cursor})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(rows[2].id)]
    assert response.json()["next_cursor"] is None
    legacy = await page_client.get("/todos", params={"limit": 2, "offset": 1})
    assert legacy.status_code == 200
    assert [item["id"] for item in legacy.json()] == [str(row.id) for row in rows[1:]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params", [{"cursor": "invalid"}, {"cursor": ""}, {"limit": 0}, {"limit": 1001}]
)
async def test_page_route_rejects_invalid_cursor_and_unbounded_limits(
    page_sql, page_client, params
):
    response = await page_client.get("/todos/page", params=params)
    assert response.status_code == 422
    page_sql[1].execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_page_has_no_cursor(page_client):
    response = await page_client.get("/todos/page")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}
