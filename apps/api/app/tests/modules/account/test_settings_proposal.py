from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models import model_catalog
from app.modules.account.settings_intent import SettingsChange
from app.modules.account.settings_proposal import (
    SettingsProposalError,
    change_label,
    confirm_proposal,
    format_proposal_reply,
    materialize_memory_reset_reply,
    materialize_settings_reply,
    validate_changes,
)
from app.tests.fakes import redis_mock


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
        "app.modules.account.settings_proposal.plan_service.allowed_model_ids",
        lambda _user, _settings: {"free-chat"},
    )
    apply, already, blocked = validate_changes(
        user,  # type: ignore[arg-type]
        settings,
        [SettingsChange("default_model", "gpt-6-sol")],
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
    redis = redis_mock()
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
    redis = redis_mock()
    redis.set = AsyncMock(return_value=True)
    redis.getdel = AsyncMock(return_value=b"1")
    redis.get = AsyncMock(
        return_value=b'[{"field":"response_tone","value":"casual"},{"field":"appearance","value":"dark"}]'
    )
    session = AsyncMock()
    settings = MagicMock()
    updated = _user(response_tone="casual")

    from app.modules.account import settings_proposal as svc

    monkeypatch.setattr(svc.users_repo, "update", AsyncMock(return_value=updated))
    result = await confirm_proposal(session, redis, user, settings, "pid")  # type: ignore[arg-type]

    assert result["appearance"] == "dark"
    assert result["user"].response_tone == "casual"
    assert {item["field"] for item in result["applied"]} == {"response_tone", "appearance"}


@pytest.mark.asyncio
async def test_confirm_expired_raises() -> None:
    redis = redis_mock()
    redis.get = AsyncMock(return_value=None)
    with pytest.raises(SettingsProposalError):
        await confirm_proposal(AsyncMock(), redis, _user(), MagicMock(), "gone")  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reset", "lead", "label"),
    [
        ("clear", "I can delete everything Recall has saved about you.", "Delete everything saved"),
        ("off", "I can turn memory off", "Off"),
    ],
)
async def test_a_memory_reset_is_a_card_to_tap(reset, lead, label) -> None:
    """M10: "forget everything you know about me" is a confirm card, not a silent wipe."""
    redis = redis_mock()
    reply = await materialize_memory_reset_reply(
        redis,
        _user(),  # type: ignore[arg-type]
        MagicMock(),
        reset,
    )
    assert reply is not None
    assert reply.startswith(lead)
    assert "Settings → Memory" in reply
    assert "```settings_proposal" in reply
    assert f'"label": "{label}"' in reply
    redis.set.assert_awaited()


@pytest.mark.asyncio
async def test_turning_memory_off_when_it_is_off_says_so() -> None:
    reply = await materialize_memory_reset_reply(
        AsyncMock(),
        _user(memory_enabled=False),  # type: ignore[arg-type]
        MagicMock(),
        "off",
    )
    assert reply == "Memory is already off. You can turn it back on in Settings → Memory."


@pytest.mark.asyncio
@pytest.mark.parametrize("reset", ["clear", "off"])
async def test_confirming_a_memory_reset_applies_it(monkeypatch: pytest.MonkeyPatch, reset) -> None:
    user = _user()
    redis = redis_mock()
    redis.set = AsyncMock(return_value=True)
    redis.getdel = AsyncMock(return_value=b"1")
    redis.get = AsyncMock(return_value=f'[{{"field":"memory","value":"{reset}"}}]'.encode())

    from app.modules.account import settings_proposal as svc

    update = AsyncMock(return_value=_user(memory_enabled=False))
    clear = AsyncMock(return_value=3)
    monkeypatch.setattr(svc.users_repo, "update", update)
    monkeypatch.setattr(svc.memory_service, "invalidate_memory_block", AsyncMock())
    monkeypatch.setattr(svc.memory_service, "delete_all_memories", clear)

    result = await confirm_proposal(AsyncMock(), redis, user, MagicMock(), "pid")  # type: ignore[arg-type]

    assert [item["field"] for item in result["applied"]] == ["memory"]
    if reset == "off":
        update.assert_awaited_once()
        assert update.await_args is not None
        assert update.await_args.kwargs == {"memory_enabled": False}
        clear.assert_not_awaited()
    else:
        clear.assert_awaited_once()
        update.assert_not_awaited()


def test_a_model_card_shows_the_name_settings_shows() -> None:
    # The card read its own labels ("Flash", "Pro") while Settings → Models showed the
    # catalog's (code-health audit ARCH-06).
    assert change_label("default_model", "auto") == "Auto"
    for model in model_catalog.selectable_models():
        assert change_label("default_model", model.id) == model.label
