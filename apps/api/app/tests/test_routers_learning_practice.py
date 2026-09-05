from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_db
from app.core.deps import get_current_user
from app.main import create_app
from app.models.orm import User
from app.models.schemas.learning import LearningItemOut
from app.services.projects.crud import ProjectsError


def item_out():
    return LearningItemOut(
        id=uuid4(),
        list_title="Greetings",
        content="hello",
        note=None,
        definition="A greeting.",
        example_sentence="Hello, Maya!\nI said hello to my neighbor.",
        status="learning",
        mastered=False,
        mastered_at=None,
        last_reviewed_at=datetime.now(UTC),
        review_count=0,
        pronunciation_url=None,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def route_client():
    app = create_app()
    user = User(id=uuid4(), email="learner@example.com")
    session = AsyncMock()

    async def fake_session():
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = fake_session
    return TestClient(app), user, session


@pytest.mark.parametrize("recorded", [True, False])
def test_practice_route_returns_current_item_and_retry_disposition(route_client, recorded):
    client, user, session = route_client
    project_id, item = uuid4(), item_out()
    attempt = uuid4()
    with patch(
        "app.services.learning.practice.record_practice",
        AsyncMock(return_value=(item, recorded, False)),
    ) as record:
        result = client.post(
            f"/projects/{project_id}/items/{item.id}/practice",
            json={"attempt_id": str(attempt), "was_correct": True, "completes_word": False},
        )
    assert result.status_code == 200
    assert result.json()["recorded"] is recorded
    assert result.json()["newly_mastered"] is False
    assert result.json()["item"]["example_sentences"] == [
        "Hello, Maya!",
        "I said hello to my neighbor.",
    ]
    assert record.await_args.args[:4] == (session, user.id, project_id, item.id)
    assert record.await_args.args[4].attempt_id == attempt


@pytest.mark.parametrize(
    "bad", [dict(was_correct=False, completes_word=True), dict(attempt_id="invalid")]
)
def test_invalid_practice_body_never_records(route_client, bad):
    client, _, _ = route_client
    with patch("app.services.learning.practice.record_practice", AsyncMock()) as record:
        result = client.post(
            f"/projects/{uuid4()}/items/{uuid4()}/practice",
            json=dict(attempt_id=str(uuid4()), was_correct=True, completes_word=False) | bad,
        )
    assert result.status_code == 422
    record.assert_not_awaited()


@pytest.mark.parametrize("code", [404, 409])
def test_practice_route_preserves_ownership_and_retry_conflict_errors(route_client, code):
    client, _, _ = route_client
    with patch(
        "app.services.learning.practice.record_practice",
        AsyncMock(side_effect=ProjectsError("unavailable", status_code=code)),
    ):
        result = client.post(
            f"/projects/{uuid4()}/items/{uuid4()}/practice",
            json=dict(attempt_id=str(uuid4()), was_correct=True, completes_word=False),
        )
    assert result.status_code == code
