"""Taking a model out of the catalog needs no data migration (review 2026-11-12 §3.2).

A user whose saved model was removed, with Auto off, could neither send (the phone sent
the dead alias and the request failed validation) nor fix Settings (the whole list was
refused before the cleanup that drops it). Removal is simulated by taking an alias out
of the catalog for the test.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.exceptions import UnknownModelOverrideError
from app.models import model_catalog, model_removal
from app.models.model_removal import REMOVED_ALIASES, current_choices, requested_choice
from app.models.schemas.auth import UserOut, UserUpdate
from app.models.schemas.chats import ChatCreate, ChatMessageRequest
from app.modules.billing import plan
from app.modules.chat.model_routing.choice import resolve_user_model_override
from app.tests.api_support import api_user, app_with_user
from app.tests.fakes import isolated_settings

# A free-plan model only a maths backup lane names: the least coupled one to remove.
REMOVED = "glm-5.3-flash"


@pytest.fixture
def removed(monkeypatch: pytest.MonkeyPatch) -> str:
    """The catalog as it would be with ``REMOVED`` deleted from it and its alias listed as
    removed, as a removal does both."""
    kept = tuple(model for model in model_catalog.CATALOG if model.id != REMOVED)
    monkeypatch.setattr(model_catalog, "CATALOG", kept)
    monkeypatch.setattr(model_catalog, "_BY_ID", {model.id: model for model in kept})
    monkeypatch.setattr(model_removal, "REMOVED_ALIASES", REMOVED_ALIASES | {REMOVED})
    return REMOVED


@pytest.mark.parametrize(
    ("saved", "current"),
    [
        (None, None),
        ([], None),
        (["auto"], ["auto"]),
        ([REMOVED], None),
        (["auto", REMOVED], ["auto"]),
        ([REMOVED, "free-chat", "qwen-3.7-flash"], ["free-chat", "qwen-3.7-flash"]),
        # Not a model the Settings switches can hold: an internal lane.
        (["title-model", "free-chat"], ["free-chat"]),
    ],
)
def test_current_choices_drops_models_the_catalog_no_longer_offers(
    removed: str, saved: list[str] | None, current: list[str] | None
) -> None:
    assert current_choices(saved) == current


def test_current_choices_keeps_every_offered_model() -> None:
    offered = ["auto", *(model.id for model in model_catalog.selectable_models())]
    assert current_choices(offered) == offered


@pytest.mark.parametrize(
    ("value", "choice"), [("auto", "auto"), ("free-chat", "free-chat"), (REMOVED, "auto")]
)
def test_a_request_naming_a_removed_model_is_auto(removed: str, value: str, choice: str) -> None:
    assert requested_choice(value) == choice
    assert ChatMessageRequest.model_validate({"model": value}).model == choice
    assert ChatCreate.model_validate({"model": value}).model == choice


@pytest.mark.parametrize(
    "value",
    # Shaped like an alias or not, a name the catalog never had is refused: a typo of a
    # real alias, another app's model, a made-up lane (review of PR #2420).
    [
        "smart-chta",
        "fake-model",
        "gpt-4o",
        "image-search-model",
        "not-a-model",
        "Not A Model!",
        "",
        "x" * 80,
        "free chat",
    ],
)
def test_a_name_no_alias_ever_had_is_still_refused(value: str) -> None:
    with pytest.raises(ValidationError, match="Unknown model alias"):
        ChatMessageRequest.model_validate({"model": value})
    with pytest.raises(ValidationError, match="Unknown model alias"):
        UserUpdate(default_model=value)
    with pytest.raises(ValidationError, match="Unknown model alias"):
        UserUpdate(enabled_models=["auto", value])


def test_a_removed_alias_is_one_the_catalog_no_longer_has() -> None:
    """An alias brought back is the catalog's again, and every catalog alias is itself."""
    assert not REMOVED_ALIASES & model_catalog.known_ids()
    for alias in model_catalog.known_ids():
        assert requested_choice(alias) == alias
    for alias in REMOVED_ALIASES:
        assert requested_choice(alias) == "auto"


def _user_out(enabled: list[str] | None) -> UserOut:
    return UserOut.model_validate(api_user(enabled_models=enabled))


def test_the_profile_never_hands_the_phone_a_removed_model(removed: str) -> None:
    alone = _user_out([removed])
    assert alone.enabled_models is None
    assert alone.default_model == "auto"
    beside = _user_out([removed, "free-chat"])
    assert beside.enabled_models == ["free-chat"]
    assert beside.default_model == "free-chat"


def test_get_me_shows_a_valid_model_after_a_removal(removed: str) -> None:
    user = api_user(enabled_models=[removed, "qwen-3.7-flash"])
    body = TestClient(app_with_user(user)).get("/auth/me", headers={"Authorization": "Bearer t"})
    assert body.status_code == 200
    assert body.json()["enabled_models"] == ["qwen-3.7-flash"]
    assert body.json()["default_model"] == "qwen-3.7-flash"


def _patch_me(user: MagicMock, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    captured: dict[str, Any] = {}

    async def capture(_session: object, _user: object, **fields: Any) -> MagicMock:
        captured.update(fields)
        return user

    with (
        patch("app.modules.account.lifecycle.users_repo.update", AsyncMock(side_effect=capture)),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        response = TestClient(app_with_user(user)).patch(
            "/auth/me", headers={"Authorization": "Bearer t"}, json=body
        )
    return response.status_code, captured


def test_settings_save_the_list_the_phone_sends_back_without_the_removed_model(
    removed: str,
) -> None:
    user = api_user(enabled_models=[removed, "free-chat"])
    status, captured = _patch_me(user, {"enabled_models": ["auto", removed, "free-chat"]})
    assert status == 200
    assert captured["enabled_models"] == ["auto", "free-chat"]


def test_settings_still_need_auto_or_a_model(removed: str) -> None:
    with pytest.raises(ValidationError, match="Turn on Auto or at least one model"):
        UserUpdate(enabled_models=[removed])
    with pytest.raises(ValidationError, match="Turn on Auto or at least one model"):
        UserUpdate(enabled_models=[])


def test_an_older_app_choosing_a_removed_model_turns_auto_on(removed: str) -> None:
    status, captured = _patch_me(api_user(enabled_models=["free-chat"]), {"default_model": removed})
    assert status == 200
    assert captured["enabled_models"][0] == "auto"


def test_a_mistyped_model_is_refused_and_leaves_auto_off() -> None:
    """A typo of a real alias was read as a removed model and switched Auto on."""
    status, captured = _patch_me(
        api_user(enabled_models=["free-chat"]), {"default_model": "smart-chta"}
    )
    assert status == 422
    assert captured == {}


def test_a_message_naming_the_removed_model_gets_an_answer(removed: str) -> None:
    """The stuck user: Auto off, the removed model first, the phone sending it."""
    settings = isolated_settings(mock_llm_enabled=True)
    request = ChatMessageRequest.model_validate({"content": "hi", "model": removed})
    alone = api_user(enabled_models=[removed])
    assert plan.is_auto_enabled(alone)
    model = resolve_user_model_override(alone, request.model, "hi", settings)
    assert model in plan.model_pool(alone, settings)
    beside = api_user(enabled_models=[removed, "free-chat"])
    assert not plan.is_auto_enabled(beside)
    assert resolve_user_model_override(beside, request.model, "hi", settings) == "free-chat"


def test_a_model_outside_the_plan_is_still_refused(removed: str) -> None:
    settings = isolated_settings(mock_llm_enabled=True)
    free = api_user(plan="free", enabled_models=[removed, "free-chat"])
    request = ChatMessageRequest.model_validate({"content": "hi", "model": "smart-chat"})
    with pytest.raises(UnknownModelOverrideError):
        resolve_user_model_override(free, request.model, "hi", settings)
