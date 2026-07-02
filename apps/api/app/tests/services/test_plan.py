"""Tests for app.services.plan — plan gates and model pools."""

from app.core.config import Settings
from app.services import plan as plan_service


class FakeUser:
    plan = "free"
    enabled_models = None


class ProUser(FakeUser):
    plan = "pro"
    enabled_models = ["auto", "free-chat", "smart-chat"]


class ManualUser(FakeUser):
    enabled_models = ["free-chat"]


def test_free_pool_uses_cheapest_models():
    settings = Settings(mock_llm_enabled=True)
    pool = plan_service.free_pool(settings)
    assert "free-chat" in pool
    assert "smart-chat" not in pool


def test_free_user_auto_routes_within_pool():
    user = FakeUser()
    settings = Settings(mock_llm_enabled=True)
    resolved = plan_service.resolve_user_model(user, "explain quantum physics", settings)
    assert resolved in plan_service.free_pool(settings)


def test_pro_user_respects_enabled_models():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True)
    assert plan_service.resolve_user_model(user, "hi", settings) == "free-chat"
    user.enabled_models = ["auto", "smart-chat"]
    assert plan_service.resolve_user_model(user, "hi", settings) == "smart-chat"


def test_pro_user_auto_can_pick_smart():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True)
    resolved = plan_service.resolve_user_model(user, "explain gravity", settings)
    assert resolved == "smart-chat"


def test_manual_mode_uses_fixed_model():
    user = ManualUser()
    user.plan = "pro"
    user.enabled_models = ["free-chat"]
    settings = Settings(mock_llm_enabled=True)
    assert plan_service.resolve_user_model(user, "explain gravity", settings) == "free-chat"


def test_is_auto_enabled_defaults_true():
    user = FakeUser()
    assert plan_service.is_auto_enabled(user) is True


def test_free_user_can_customize_enabled_models():
    user = FakeUser()
    settings = Settings(mock_llm_enabled=True)
    cleaned = plan_service.validate_enabled_models_for_update(
        user,
        ["auto", "free-chat"],
        settings,
    )
    assert cleaned == ["auto", "free-chat"]


def test_validate_enabled_models_rejects_pro_model_on_free_plan():
    user = FakeUser()
    settings = Settings(mock_llm_enabled=True)
    cleaned = plan_service.validate_enabled_models_for_update(
        user,
        ["auto", "smart-chat", "free-chat"],
        settings,
    )
    assert cleaned == ["auto", "free-chat"]


def test_override_uses_requested_model_when_allowed():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True)
    resolved = plan_service.resolve_user_model_override(user, "smart-chat", "hi", settings)
    assert resolved == "smart-chat"


def test_override_falls_back_when_alias_is_auto():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True)
    # "auto" should not be returned as-is; it routes within the pool.
    resolved = plan_service.resolve_user_model_override(user, "auto", "hi", settings)
    assert resolved in plan_service.model_pool(user, settings)


def test_override_ignores_pro_model_on_free_plan():
    user = FakeUser()  # free plan
    settings = Settings(mock_llm_enabled=True)
    # smart-chat is pro-only; free user can't override to it — falls back.
    resolved = plan_service.resolve_user_model_override(user, "smart-chat", "hi", settings)
    assert resolved != "smart-chat"
    assert resolved in plan_service.free_pool(settings)


def test_override_none_falls_back_to_resolve_user_model():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True)
    resolved = plan_service.resolve_user_model_override(user, None, "hi", settings)
    assert resolved == plan_service.resolve_user_model(user, "hi", settings)


def test_chat_fallback_models_skips_primary_and_respects_pool():
    user = ProUser()
    settings = Settings(mock_llm_enabled=True)
    fallbacks = plan_service.chat_fallback_models(user, settings, "smart-chat")
    assert "smart-chat" not in fallbacks
    assert fallbacks
    assert fallbacks[0] in plan_service.model_pool(user, settings)


def test_chat_fallback_models_empty_when_only_one_model():
    user = ManualUser()
    settings = Settings(mock_llm_enabled=True)
    assert plan_service.chat_fallback_models(user, settings, "free-chat") == []
