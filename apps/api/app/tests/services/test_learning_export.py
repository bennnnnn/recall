import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.orm import LearningPracticeEvent
from app.repositories import learning_export
from app.services import export_service


@pytest.mark.asyncio
async def test_practice_export_filters_owner_and_pages_equal_timestamps_without_duplicates():
    engine = create_engine("sqlite://")
    LearningPracticeEvent.__table__.create(engine)
    owner, outsider = uuid4(), uuid4()
    when = datetime(2026, 9, 4, 12)
    try:
        with Session(engine) as sync:
            for index, user_id in enumerate([owner, outsider, owner, owner, owner], 1):
                sync.add(
                    LearningPracticeEvent(
                        id=UUID(f"a0000000-0000-4000-8000-{index:012d}"),
                        attempt_id=uuid4(),
                        user_id=user_id,
                        project_id=uuid4(),
                        item_id=uuid4(),
                        was_correct=True,
                        completes_word=True,
                        occurred_at=when + (timedelta(days=1) if index == 5 else timedelta()),
                    )
                )
            sync.commit()
            session = AsyncMock(spec=AsyncSession)
            session.execute.side_effect = sync.execute
            first = await learning_export.list_page(session, owner, through=when, limit=2)
            assert [int(event.id.hex[-12:]) for event in first] == [1, 3]
            last = first[-1]
            second = await learning_export.list_page(
                session,
                owner,
                through=when,
                limit=2,
                after=(last.occurred_at, last.id),
            )
            assert [int(event.id.hex[-12:]) for event in second] == [4]
            assert all(event.user_id == owner for event in [*first, *second])
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_export_caps_practice_history_and_releases_session_before_yielding(monkeypatch):
    now = datetime(2026, 9, 4, tzinfo=UTC)
    user = SimpleNamespace(id=uuid4(), email="learner@example.test", name="Learner", created_at=now)
    events = [
        SimpleNamespace(
            id=UUID(int=index),
            attempt_id=uuid4(),
            project_id=uuid4(),
            item_id=uuid4(),
            was_correct=bool(index % 2),
            completes_word=False,
            newly_mastered=False,
            occurred_at=now,
        )
        for index in range(1, 5)
    ]
    for repo, method in [
        (export_service.chats_repo, "list_for_user"),
        (export_service.memories_repo, "list_range"),
        (export_service.todos_repo, "list_for_user"),
        (export_service.projects_repo, "list_for_user"),
        (export_service.attachments_repo, "list_for_user"),
        (export_service.product_events_repo, "list_for_user"),
    ]:
        monkeypatch.setattr(repo, method, AsyncMock(return_value=[]))
    monkeypatch.setattr(export_service, "EXPORT_MAX_LEARNING_PRACTICE_EVENTS", 3)
    monkeypatch.setattr(export_service, "EXPORT_LEARNING_PRACTICE_PAGE_SIZE", 2)
    monkeypatch.setattr(export_service, "get_storage_gateway", lambda settings: object())
    reads = []
    open_sessions = 0

    @asynccontextmanager
    async def factory():
        nonlocal open_sessions
        open_sessions += 1
        try:
            yield object()
        finally:
            open_sessions -= 1

    async def page(session, user_id, *, through, limit, after):
        assert open_sessions == 1
        assert user_id == user.id
        reads.append((through, limit, after))
        start = after[1].int if after else 0
        return events[start : start + limit]

    monkeypatch.setattr(learning_export, "list_page", page)
    chunks = []
    async for chunk in export_service._iter_export_json(user, Settings(), session_factory=factory):
        assert open_sessions == 0
        chunks.append(chunk)
    data = json.loads("".join(chunks))
    assert [event["id"] for event in data["learning_practice_events"]] == [
        str(event.id) for event in events[:3]
    ]
    assert [read[1] for read in reads] == [2, 1]
    assert reads[1][2] == (now, events[1].id)
    assert reads[0][0] == reads[1][0]
    assert data["export_limits"]["max_learning_practice_events"] == 3
