"""Tests for app.services.plan — plan gates and model pools."""

from app.core.config import Settings
from app.services import plan as plan_service


class FakeUser:
    plan = "free"
    enabled_models: list[str] | None = None


class ProUser(FakeUser):
    plan = "pro"
    enabled_models = ["auto", "free-chat", "smart-chat"]


class ManualUser(FakeUser):
    enabled_models = ["free-chat"]


def test_free_pool_uses_cheapest_models():
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    pool = plan_service.free_pool(settings)
    assert "free-chat" in pool
    assert "smart-chat" not in pool


def test_free_user_auto_routes_within_pool():
    user = FakeUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_user_model(user, "explain quantum physics", settings)
    assert resolved in plan_service.free_pool(settings)


def test_pro_user_respects_enabled_models():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    assert plan_service.resolve_user_model(user, "hi", settings) == "free-chat"
    user.enabled_models = ["auto", "smart-chat"]
    assert plan_service.resolve_user_model(user, "hi", settings) == "smart-chat"


def test_pro_user_auto_can_pick_smart():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_user_model(user, "debug this crash", settings)
    assert resolved == "smart-chat"


def test_manual_mode_uses_fixed_model():
    user = ManualUser()
    user.plan = "pro"
    user.enabled_models = ["free-chat"]
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    assert plan_service.resolve_user_model(user, "explain gravity", settings) == "free-chat"


def test_is_auto_enabled_defaults_true():
    user = FakeUser()
    assert plan_service.is_auto_enabled(user) is True


def test_free_user_can_customize_enabled_models():
    user = FakeUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    cleaned = plan_service.validate_enabled_models_for_update(
        user,
        ["auto", "free-chat"],
        settings,
    )
    assert cleaned == ["auto", "free-chat"]


def test_validate_enabled_models_rejects_pro_model_on_free_plan():
    user = FakeUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    cleaned = plan_service.validate_enabled_models_for_update(
        user,
        ["auto", "smart-chat", "free-chat"],
        settings,
    )
    assert cleaned == ["auto", "free-chat"]


def test_override_uses_requested_model_when_allowed():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_user_model_override(user, "smart-chat", "hi", settings)
    assert resolved == "smart-chat"


def test_override_falls_back_when_alias_is_auto():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    # "auto" should not be returned as-is; it routes within the pool.
    resolved = plan_service.resolve_user_model_override(user, "auto", "hi", settings)
    assert resolved in plan_service.model_pool(user, settings)


def test_override_ignores_pro_model_on_free_plan():
    user = FakeUser()  # free plan
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    # smart-chat is pro-only; free user can't override to it — falls back.
    resolved = plan_service.resolve_user_model_override(user, "smart-chat", "hi", settings)
    assert resolved != "smart-chat"
    assert resolved in plan_service.free_pool(settings)


def test_override_none_falls_back_to_resolve_user_model():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_user_model_override(user, None, "hi", settings)
    assert resolved == plan_service.resolve_user_model(user, "hi", settings)


def test_override_respects_disabled_in_enabled_models():
    """A pro user who disabled smart-chat in Settings can't override to it."""
    user = ProUser()
    user.enabled_models = ["auto", "free-chat"]  # smart-chat disabled
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_user_model_override(user, "smart-chat", "hi", settings)
    # smart-chat is plan-allowed but not enabled → rejected → routes within pool.
    assert resolved != "smart-chat"
    assert resolved in plan_service.model_pool(user, settings)


def test_override_allowed_when_enabled_models_is_none():
    """Default user (enabled_models=None) keeps the full plan pool."""
    user = ProUser()
    user.enabled_models = None
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_user_model_override(user, "smart-chat", "hi", settings)
    assert resolved == "smart-chat"


def test_regenerate_auto_reuses_prior_assistant_model():
    """auto + a prior smart-chat reply → regenerate reuses smart-chat, not re-route."""
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    # "debug this crash" auto-routes to smart-chat; regenerate should reuse it
    # even though the picker sent "auto" (which would otherwise re-run routing).
    resolved = plan_service.resolve_regenerate_model(
        user, "auto", "debug this crash", "smart-chat", settings
    )
    assert resolved == "smart-chat"


def test_regenerate_explicit_override_beats_prior_model():
    """An explicit concrete pick wins over the prior assistant model."""
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_regenerate_model(
        user, "free-chat", "debug this crash", "smart-chat", settings
    )
    assert resolved == "free-chat"


def test_regenerate_auto_falls_back_when_prior_model_unavailable():
    """If the prior model is no longer in the pool (e.g. downgrade), re-route."""
    user = FakeUser()  # free plan — smart-chat not allowed
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_regenerate_model(user, "auto", "hi", "smart-chat", settings)
    assert resolved != "smart-chat"
    assert resolved in plan_service.free_pool(settings)


def test_regenerate_auto_falls_back_when_prior_model_disabled():
    """Pro user disabled smart-chat after the first reply → regenerate re-routes."""
    user = ProUser()
    user.enabled_models = ["auto", "free-chat"]  # smart-chat disabled
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_regenerate_model(
        user, "auto", "debug this crash", "smart-chat", settings
    )
    assert resolved != "smart-chat"
    assert resolved in plan_service.model_pool(user, settings)


def test_regenerate_auto_none_prior_falls_back_to_routing():
    """No prior assistant model (e.g. first turn failed) → normal routing."""
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_regenerate_model(
        user, "auto", "debug this crash", None, settings
    )
    assert resolved == plan_service.resolve_user_model(user, "debug this crash", settings)


def test_regenerate_auto_prior_is_auto_falls_back_to_routing():
    """If the stored prior model is itself "auto" (shouldn't happen), re-route."""
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_regenerate_model(
        user, "auto", "debug this crash", "auto", settings
    )
    assert resolved == plan_service.resolve_user_model(user, "debug this crash", settings)


def test_regenerate_ignores_pro_prior_model_on_free_plan():
    """Free user can't reuse a pro-only prior model — falls back to free pool."""
    user = FakeUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    resolved = plan_service.resolve_regenerate_model(user, "auto", "hi", "smart-chat", settings)
    assert resolved != "smart-chat"
    assert resolved in plan_service.free_pool(settings)


def test_chat_fallback_models_skips_primary_and_respects_pool():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    fallbacks = plan_service.chat_fallback_models(user, settings, "smart-chat")
    assert "smart-chat" not in fallbacks
    assert fallbacks
    assert fallbacks[0] in plan_service.model_pool(user, settings)


def test_chat_fallback_models_empty_when_only_one_model():
    user = ManualUser()
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    assert plan_service.chat_fallback_models(user, settings, "free-chat") == []
