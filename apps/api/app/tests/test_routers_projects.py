"""Projects router tests."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_settings_dep
from app.main import create_app
from app.models.orm import User


def _fake_user() -> User:
    u = MagicMock(spec=User)
    u.id = uuid4()
    u.email = "test@recall.local"
    u.timezone = "UTC"
    return u


def _app_with_user(user: User):
    from app.core.deps import get_current_user

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: Settings()
    return app


def _project(**kw):
    p = MagicMock()
    p.id = kw.get("id", uuid4())
    p.user_id = kw.get("user_id", uuid4())
    p.title = kw.get("title", "Spanish")
    p.description = kw.get("description", "Daily vocab")
    p.kind = kw.get("kind", "language")
    p.target_language = kw.get("target_language", "en")
    p.native_language = kw.get("native_language", "en")
    p.level = kw.get("level", "level1")
    p.archived = False
    p.created_at = datetime(2024, 1, 1)
    p.updated_at = datetime(2024, 1, 1)
    return p


def _item(project_id, **kw):
    item = MagicMock()
    item.id = kw.get("id", uuid4())
    item.project_id = project_id
    item.list_title = kw.get("list_title", "General")
    item.content = kw.get("content", "hola")
    item.definition = kw.get("definition", "hello")
    item.example_sentence = None
    item.note = None
    item.status = kw.get("status", "new")
    item.mastered = kw.get("mastered", False)
    item.created_at = datetime(2024, 1, 1)
    item.last_reviewed_at = None
    item.mastered_at = None
    item.review_count = 0
    item.pronunciation_url = None
    return item


def test_list_projects():
    user = _fake_user()
    app = _app_with_user(user)
    project = _project()

    with (
        patch(
            "app.routers.projects.projects_repo.list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch(
            "app.routers.projects.project_items_repo.count_stats_by_project",
            AsyncMock(return_value={project.id: {"mastered_count": 3, "mastered_today": 1}}),
        ),
    ):
        client = TestClient(app)
        r = client.get("/projects", headers={"Authorization": "Bearer tok"})

    assert r.status_code == 200
    assert r.json()[0]["title"] == "Spanish"
    assert r.json()[0]["stats"]["mastered_count"] == 3


def test_create_project_maps_vocabulary_to_language():
    user = _fake_user()
    app = _app_with_user(user)
    project = _project(kind="language")

    with (
        patch(
            "app.routers.projects.projects_repo.create",
            AsyncMock(return_value=project),
        ) as create_mock,
        patch(
            "app.routers.projects.projects_repo.find_language_by_target",
            AsyncMock(return_value=None),
        ),
    ):
        client = TestClient(app)
        r = client.post(
            "/projects",
            headers={"Authorization": "Bearer tok"},
            json={"title": "French", "kind": "vocabulary"},
        )

    assert r.status_code == 201
    assert create_mock.await_args.kwargs["kind"] == "language"


def test_create_language_project_rejects_duplicate():
    user = _fake_user()
    app = _app_with_user(user)
    existing = _project(kind="language", title="English · Beginner")

    with (
        patch(
            "app.routers.projects.projects_repo.find_language_by_target",
            AsyncMock(return_value=existing),
        ),
        patch(
            "app.routers.projects.projects_repo.create",
            AsyncMock(),
        ) as create_mock,
    ):
        client = TestClient(app)
        r = client.post(
            "/projects",
            headers={"Authorization": "Bearer tok"},
            json={"title": "English · Elementary", "kind": "language", "level": "level2"},
        )

    assert r.status_code == 409
    create_mock.assert_not_awaited()


def test_create_programming_project_rejected():
    user = _fake_user()
    app = _app_with_user(user)

    with patch(
        "app.routers.projects.projects_repo.create",
        AsyncMock(),
    ) as create_mock:
        client = TestClient(app)
        r = client.post(
            "/projects",
            headers={"Authorization": "Bearer tok"},
            json={
                "title": "Python · Programming",
                "kind": "programming",
                "target_language": "python",
            },
        )

    assert r.status_code == 400
    assert r.json()["detail"] == "programming_not_supported"
    create_mock.assert_not_awaited()


def test_patch_programming_kind_rejected():
    user = _fake_user()
    app = _app_with_user(user)
    project = _project(kind="language", title="Spanish")

    with (
        patch(
            "app.routers.projects.projects_repo.get_by_id",
            AsyncMock(return_value=project),
        ),
        patch(
            "app.routers.projects.projects_repo.update",
            AsyncMock(),
        ) as update_mock,
    ):
        client = TestClient(app)
        r = client.patch(
            f"/projects/{project.id}",
            headers={"Authorization": "Bearer tok"},
            json={"kind": "programming"},
        )

    assert r.status_code == 400
    assert r.json()["detail"] == "programming_not_supported"
    update_mock.assert_not_awaited()


def test_create_trivia_project_rejects_duplicate():
    user = _fake_user()
    app = _app_with_user(user)
    existing = _project(kind="trivia", title="General knowledge")

    with (
        patch(
            "app.routers.projects.projects_repo.find_trivia_project",
            AsyncMock(return_value=existing),
        ),
        patch(
            "app.routers.projects.projects_repo.create",
            AsyncMock(),
        ) as create_mock,
    ):
        client = TestClient(app)
        r = client.post(
            "/projects",
            headers={"Authorization": "Bearer tok"},
            json={
                "title": "General knowledge",
                "kind": "trivia",
                "description": "history,science",
                "daily_goal": 10,
            },
        )

    assert r.status_code == 409
    assert r.json()["detail"] == "trivia_project_exists"
    create_mock.assert_not_awaited()


def test_get_programming_project_not_found():
    user = _fake_user()
    app = _app_with_user(user)
    project = _project(kind="programming", title="JS")
    project_id = project.id

    with patch(
        "app.routers.projects.projects_repo.get_by_id",
        AsyncMock(return_value=project),
    ):
        client = TestClient(app)
        r = client.get(f"/projects/{project_id}", headers={"Authorization": "Bearer tok"})

    assert r.status_code == 404


def test_get_project_not_found():
    user = _fake_user()
    app = _app_with_user(user)

    with patch(
        "app.routers.projects.projects_repo.get_by_id",
        AsyncMock(return_value=None),
    ):
        client = TestClient(app)
        r = client.get(f"/projects/{uuid4()}", headers={"Authorization": "Bearer tok"})

    assert r.status_code == 404


def test_get_language_project_detail():
    user = _fake_user()
    app = _app_with_user(user)
    project = _project(kind="language")
    project_id = project.id
    noun = _item(project_id)
    noun.list_title = "General"
    noun.content = "apple"
    verb = _item(project_id)
    verb.list_title = "General"
    verb.content = "run"

    with (
        patch(
            "app.routers.projects.projects_repo.get_by_id",
            AsyncMock(return_value=project),
        ),
        patch(
            "app.routers.projects.project_items_repo.list_for_user",
            AsyncMock(return_value=[noun, verb]),
        ),
        patch(
            "app.routers.projects.project_items_repo.stats_from_items",
            return_value={
                "total": 2,
                "mastered_count": 1,
                "new_count": 1,
                "learning_count": 0,
                "added_this_week": 1,
                "due_for_review": 1,
                "mastered_today": 0,
                "pending_today": 0,
                "last_mastery_at": None,
            },
        ),
    ):
        client = TestClient(app)
        r = client.get(f"/projects/{project_id}", headers={"Authorization": "Bearer tok"})

    assert r.status_code == 200
    body = r.json()
    assert body["total_count"] == 2
    assert len(body["lists"]) >= 1
    assert len(body["daily_history"]) == 14


def test_list_daily_items():
    user = _fake_user()
    app = _app_with_user(user)
    project = _project(kind="language")
    project_id = project.id
    item = _item(project_id)

    with (
        patch(
            "app.routers.projects.projects_repo.get_by_id",
            AsyncMock(return_value=project),
        ),
        patch(
            "app.routers.projects.project_items_repo.list_by_activity_date",
            AsyncMock(return_value=[item]),
        ),
    ):
        client = TestClient(app)
        r = client.get(
            f"/projects/{project_id}/daily-items?activity_date=2026-07-01",
            headers={"Authorization": "Bearer tok"},
        )

    assert r.status_code == 200
    assert r.json()[0]["content"] == "hola"


def test_update_project_daily_goal():
    user = _fake_user()
    app = _app_with_user(user)
    project = _project(kind="language")
    project.daily_goal = 5
    project.daily_goal_history = [{"effective_from": "2026-07-07", "goal": 5}]
    project.created_at = datetime(2026, 7, 7, tzinfo=UTC)
    project_id = project.id
    updated = _project(kind="language")
    updated.daily_goal = 15

    with (
        patch(
            "app.routers.projects.projects_repo.get_by_id",
            AsyncMock(return_value=project),
        ),
        patch(
            "app.routers.projects.projects_repo.update",
            AsyncMock(return_value=updated),
        ) as update_mock,
        patch("app.routers.projects.home_service.invalidate_home_cache", AsyncMock()),
        patch(
            "app.routers.projects.datetime",
        ) as dt_mock,
    ):
        dt_mock.now.return_value = datetime(2026, 7, 8, 12, tzinfo=UTC)
        client = TestClient(app)
        r = client.patch(
            f"/projects/{project_id}",
            headers={"Authorization": "Bearer tok"},
            json={"daily_goal": 15},
        )

    assert r.status_code == 200
    assert update_mock.await_args.kwargs["daily_goal"] == 15
    history = update_mock.await_args.kwargs["daily_goal_history"]
    assert history[-1]["goal"] == 15
    assert r.json()["daily_goal"] == 15


def test_update_project_maps_vocabulary_kind():
    user = _fake_user()
    app = _app_with_user(user)
    project = _project()
    project_id = project.id
    updated = _project(kind="language")

    with (
        patch(
            "app.routers.projects.projects_repo.get_by_id",
            AsyncMock(return_value=project),
        ),
        patch(
            "app.routers.projects.projects_repo.update",
            AsyncMock(return_value=updated),
        ) as update_mock,
    ):
        client = TestClient(app)
        r = client.patch(
            f"/projects/{project_id}",
            headers={"Authorization": "Bearer tok"},
            json={"kind": "vocabulary"},
        )

    assert r.status_code == 200
    assert update_mock.await_args.kwargs["kind"] == "language"


def test_delete_project_not_found():
    user = _fake_user()
    app = _app_with_user(user)

    with patch(
        "app.routers.projects.projects_repo.delete_by_id",
        AsyncMock(return_value=False),
    ):
        client = TestClient(app)
        r = client.delete(f"/projects/{uuid4()}", headers={"Authorization": "Bearer tok"})

    assert r.status_code == 404


def test_delete_project_success():
    user = _fake_user()
    app = _app_with_user(user)

    with patch(
        "app.routers.projects.projects_repo.delete_by_id",
        AsyncMock(return_value=True),
    ):
        client = TestClient(app)
        r = client.delete(f"/projects/{uuid4()}", headers={"Authorization": "Bearer tok"})

    assert r.status_code == 204


def test_update_project_item_status():
    user = _fake_user()
    app = _app_with_user(user)
    project = _project(user_id=user.id)
    item = _item(project.id, status="new")

    with (
        patch(
            "app.routers.projects.projects_repo.get_by_id",
            AsyncMock(return_value=project),
        ),
        patch(
            "app.routers.projects.project_items_repo.get_by_id",
            AsyncMock(return_value=item),
        ),
        patch(
            "app.routers.projects.project_items_repo.update",
            AsyncMock(return_value=item),
        ) as update_mock,
    ):
        client = TestClient(app)
        r = client.patch(
            f"/projects/{project.id}/items/{item.id}",
            headers={"Authorization": "Bearer tok"},
            json={"status": "mastered"},
        )

    assert r.status_code == 200
    update_mock.assert_awaited_once()
    assert update_mock.await_args.kwargs["status"] == "mastered"
