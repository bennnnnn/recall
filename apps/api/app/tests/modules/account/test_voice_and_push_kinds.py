"""PATCH /auth/me saves the voice and the per-kind push switches."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.tests.test_routers import _app_with_user, _fake_user


def _patch_me(body: dict, **updated_fields):
    user = _fake_user()
    update = AsyncMock(return_value=_fake_user(**updated_fields))
    with patch("app.modules.account.lifecycle.users_repo.update", update):
        response = TestClient(_app_with_user(user)).patch(
            "/auth/me", headers={"Authorization": "Bearer tok"}, json=body
        )
    return response, update


def test_me_reports_the_new_settings_with_defaults() -> None:
    client = TestClient(_app_with_user(_fake_user()))
    body = client.get("/auth/me", headers={"Authorization": "Bearer tok"}).json()
    assert body["push_reminders_enabled"] is True
    assert body["push_email_suggestions_enabled"] is True
    assert body["push_calendar_enabled"] is True
    assert body["tts_voice"] is None


@pytest.mark.parametrize(
    "column",
    ["push_reminders_enabled", "push_email_suggestions_enabled", "push_calendar_enabled"],
)
def test_patch_turns_one_push_kind_off(column: str) -> None:
    response, update = _patch_me({column: False}, **{column: False})
    assert response.status_code == 200
    assert response.json()[column] is False
    assert update.await_args.kwargs[column] is False


def test_patch_saves_a_voice() -> None:
    response, update = _patch_me({"tts_voice": "cedar"}, tts_voice="cedar")
    assert response.status_code == 200
    assert response.json()["tts_voice"] == "cedar"
    assert update.await_args.kwargs["tts_voice"] == "cedar"


def test_patch_null_voice_puts_the_default_back() -> None:
    response, update = _patch_me({"tts_voice": None})
    assert response.status_code == 200
    assert update.await_args.kwargs["tts_voice"] is None


@pytest.mark.parametrize("voice", ["fable", "onyx", "Kore", ""])
def test_patch_rejects_a_voice_live_talk_cannot_speak(voice: str) -> None:
    response, update = _patch_me({"tts_voice": voice})
    assert response.status_code == 422
    update.assert_not_awaited()
