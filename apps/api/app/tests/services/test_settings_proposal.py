from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.settings_intent import SettingsChange
from app.services.settings_proposal import (
    SettingsProposalError,
    confirm_proposal,
    format_proposal_reply,
    materialize_settings_reply,
    validate_changes,
)


def _user(**overrides: object) -> SimpleNamespace:
    data: dict[str, object] = {
        "id": uuid4(),
        "plan": "pro",
        "default_model": "auto",
        "enabled_models": ["auto", "free-chat", "smart-chat"],
        "response_tone": "funny",
        "locale": "en",
        "memory_enabled": True,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_validate_blocks_pro_model_on_free_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user(plan="free", enabled_models=["auto", "free-chat"])
    settings = MagicMock()
    monkeypatch.setattr(
        "app.services.settings_proposal.plan_service.allowed_model_ids",
        lambda _user, _settings: {"free-chat"},
    )
    apply, already, blocked = validate_changes(
        user,  # type: ignore[arg-type]
        settings,
        [SettingsChange("default_model", "gpt-5.5")],
    )
    assert apply == []
    assert already == []
    assert blocked is not None
    assert "plan" in blocked.lower()


def test_validate_skips_already_set_tone() -> None:
    user = _user(response_tone="professional")
    settings = MagicMock()
    apply, already, blocked = validate_changes(
        user,  # type: ignore[arg-type]
        settings,
        [SettingsChange("response_tone", "professional")],
    )
    assert apply == []
    assert already[0].value == "professional"
    assert blocked is None


def test_validate_normalizes_appearance_default_to_system() -> None:
    """The model emits appearance="default" to undo an explicit light/dark
    choice (follow the system theme). Without normalization this is silently
    dropped (not in {light,dark,system}) and confirm fails with "I couldn't
    change that setting." Normalize "default" -> "system" so it applies."""
    user = _user()
    settings = MagicMock()
    apply, _already, blocked = validate_changes(
        user,  # type: ignore[arg-type]
        settings,
        [SettingsChange("appearance", "default")],
    )
    assert blocked is None
    assert len(apply) == 1
    assert apply[0].field == "appearance"
    assert apply[0].value == "system"


def test_format_proposal_includes_fence() -> None:
    text = format_proposal_reply(
        proposal_id="abc",
        apply=[SettingsChange("appearance", "dark")],
        already=[],
    )
    assert "settings_proposal" in text
    assert "abc" in text
    assert "Dark" in text


@pytest.mark.asyncio
async def test_materialize_stores_redis() -> None:
    redis = AsyncMock()
    user = _user()
    settings = MagicMock()
    reply = await materialize_settings_reply(
        redis,
        user,  # type: ignore[arg-type]
        settings,
        [SettingsChange("appearance", "dark")],
    )
    assert reply is not None
    assert "settings_proposal" in reply
    redis.set.assert_awaited()


@pytest.mark.asyncio
async def test_confirm_applies_tone_and_appearance(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.getdel = AsyncMock(return_value=b"1")
    redis.get = AsyncMock(
        return_value=b'[{"field":"response_tone","value":"casual"},{"field":"appearance","value":"dark"}]'
    )
    session = AsyncMock()
    settings = MagicMock()
    updated = _user(response_tone="casual")

    from app.services import settings_proposal as svc

    monkeypatch.setattr(svc.users_repo, "update", AsyncMock(return_value=updated))
    monkeypatch.setattr(svc.home_service, "invalidate_home_cache", AsyncMock())
    result = await confirm_proposal(session, redis, user, settings, "pid")  # type: ignore[arg-type]

    assert result["appearance"] == "dark"
    assert result["user"].response_tone == "casual"
    assert {item["field"] for item in result["applied"]} == {"response_tone", "appearance"}


@pytest.mark.asyncio
async def test_confirm_expired_raises() -> None:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    with pytest.raises(SettingsProposalError):
        await confirm_proposal(AsyncMock(), redis, _user(), MagicMock(), "gone")  # type: ignore[arg-type]
