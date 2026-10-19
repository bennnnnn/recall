from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.db import get_db
from app.core.deps import get_current_user
from app.main import create_app
from app.models.orm import User


def _app_with_analytics_dependencies():
    user = MagicMock(spec=User)
    user.id = uuid4()
    session = AsyncMock()
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: session
    return app, user, session


def test_record_product_events_returns_204() -> None:
    app, user, session = _app_with_analytics_dependencies()
    with patch(
        "app.routers.analytics.product_analytics.record_batch",
        AsyncMock(),
    ) as record_batch:
        response = TestClient(app).post(
            "/analytics/events",
            headers={"Authorization": "Bearer token"},
            json={
                "events": [
                    {
                        "name": "paywall_viewed",
                        "properties": {"source": "quota"},
                        "platform": "ios",
                    }
                ]
            },
        )

    assert response.status_code == 204
    record_batch.assert_awaited_once()
    call = record_batch.await_args
    assert call is not None
    assert call.args[0] is session
    assert call.args[1] == user.id


def test_record_product_events_maps_property_error_to_422() -> None:
    app, _, _ = _app_with_analytics_dependencies()
    with patch(
        "app.routers.analytics.product_analytics.record_batch",
        AsyncMock(side_effect=ValueError("Invalid properties")),
    ):
        response = TestClient(app).post(
            "/analytics/events",
            headers={"Authorization": "Bearer token"},
            json={
                "events": [
                    {
                        "name": "purchase_started",
                        "properties": {},
                    }
                ]
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid properties"


def _post_turn_outcome(app, properties: dict[str, str]):
    return TestClient(app).post(
        "/analytics/events",
        headers={"Authorization": "Bearer token"},
        json={"events": [{"name": "chat_turn_outcome", "properties": properties}]},
    )


def test_chat_turn_outcome_is_accepted_with_metadata_only() -> None:
    app, _, _ = _app_with_analytics_dependencies()
    with patch(
        "app.services.product_analytics.product_events_repo.create_batch", AsyncMock()
    ) as create_batch:
        response = _post_turn_outcome(
            app, {"completion": "error", "error_code": "model_unavailable", "tool": "none"}
        )

    assert response.status_code == 204
    create_batch.assert_awaited_once()


def test_chat_turn_outcome_rejects_free_text_properties() -> None:
    """O10.1: a turn outcome carries no prompt, reply, query or provider message."""
    app, _, _ = _app_with_analytics_dependencies()
    with patch(
        "app.services.product_analytics.product_events_repo.create_batch", AsyncMock()
    ) as create_batch:
        response = _post_turn_outcome(
            app,
            {
                "completion": "complete",
                "error_code": "none",
                "tool": "searching: cheap flights to Lagos",
            },
        )

    assert response.status_code == 422
    create_batch.assert_not_awaited()
