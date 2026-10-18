import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.models.schemas import ChatCreate, UserUpdate
from app.services import model_catalog


def test_selectable_models_count():
    models = model_catalog.selectable_models()
    ids = {m.id for m in models}
    # Six chat models: three on the free plan, the rest paid.
    assert ids == {
        "qwen-3.7-flash",
        "free-chat",
        "glm-5.3-flash",
        "smart-chat",
        "glm-5.2",
        "gpt-6-luna",
    }
    assert {m.id for m in models if m.plan_access == "free"} == {
        "qwen-3.7-flash",
        "free-chat",
        "glm-5.3-flash",
    }
    assert "free-chat" in ids
    assert "gpt-6-luna" in ids
    assert "glm-5.3-flash" in ids
    assert "glm-5.2" in ids
    luna = model_catalog.get("gpt-6-luna")
    assert luna.tier == "fast"
    assert luna.model == "openrouter/openai/gpt-6-luna"
    glm = model_catalog.get("glm-5.2")
    assert glm.tier == "smart"
    assert glm.model == "openrouter/z-ai/glm-5.2"
    assert model_catalog.is_reasoning_alias("glm-5.2") is True
    assert glm.thinking_off == "none"
    assert model_catalog.get("smart-chat").thinking_off == "none"
    assert model_catalog.get("smart-chat").thinking_on == "low"
    assert luna.thinking_off == "none"
    # GPT-6 Luna stays, for the paid plans only.
    assert luna.plan_access == "pro"
    qwen = model_catalog.get("qwen-3.7-flash")
    assert qwen.tier == "fast"
    assert qwen.plan_access == "free"
    assert qwen.model == "openrouter/qwen/qwen3.7-flash"
    assert qwen.thinking_off == "off"
    assert model_catalog.auto_fast_alias() == "qwen-3.7-flash"
    # Recall is not a coding assistant: the coding and frontier models are gone.
    for removed in ("gpt-6-sol", "kimi-k3", "qwen-3.8-max", "minimax-m3", "glm-5.3", "llama-70b"):
        assert removed not in ids
    assert "max-chat" not in ids


@pytest.mark.parametrize(
    "alias, slug, input_price, output_price, tier, plan",
    [
        ("qwen-3.7-flash", "qwen/qwen3.7-flash", 0.03, 0.13, "fast", "free"),
        ("smart-chat", "deepseek/deepseek-v4.1-flash", 0.15, 0.60, "smart", "pro"),
        ("glm-5.2", "z-ai/glm-5.2", 0.62, 2.42, "smart", "pro"),
        ("gpt-6-luna", "openai/gpt-6-luna", 0.10, 0.50, "fast", "pro"),
    ],
)
def test_catalog_models_use_live_openrouter_prices(
    alias: str,
    slug: str,
    input_price: float,
    output_price: float,
    tier: str,
    plan: str,
) -> None:
    model = model_catalog.get(alias)

    assert model.model == f"openrouter/{slug}"
    assert model.input_price_per_m == input_price
    assert model.output_price_per_m == output_price
    assert model.tier == tier
    assert model.plan_access == plan
    assert model.selectable is True
    assert model_catalog.openrouter_slug(alias) == slug


def test_known_model_aliases_match_catalog():
    from app.core.validation import KNOWN_MODEL_ALIASES

    assert KNOWN_MODEL_ALIASES == model_catalog.known_ids()


def test_estimate_cost_usd_for_known_model():
    # free-chat: $0.10 / 1M in, $0.50 / 1M out
    cost = model_catalog.estimate_cost_usd(
        "free-chat",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert cost == pytest.approx(0.10 + 0.50)

    # smart-chat: $0.15 / 1M in, $0.60 / 1M out — 1k/2k tokens
    cost_small = model_catalog.estimate_cost_usd(
        "smart-chat",
        input_tokens=1_000,
        output_tokens=2_000,
    )
    assert cost_small == pytest.approx((1000 / 1_000_000) * 0.15 + (2000 / 1_000_000) * 0.60)


def test_estimate_cost_usd_unknown_or_unpriced():
    assert (
        model_catalog.estimate_cost_usd("no-such-model", input_tokens=10, output_tokens=10) is None
    )
    # The embedding alias has no catalog prices today
    assert (
        model_catalog.estimate_cost_usd("embedding-model", input_tokens=10, output_tokens=10)
        is None
    )


def test_get_unknown_alias_raises():
    with pytest.raises(KeyError, match="Unknown model alias"):
        model_catalog.get("not-a-real-model")


def test_default_model_is_free_chat():
    assert model_catalog.default_model().id == "free-chat"


def _model(tier: str, *, input_price=None, output_price=None, id_="test-model"):
    return model_catalog.ChatModel(
        id=id_,
        label="Test",
        provider="openrouter",
        model="openrouter/test/test",
        api_key_field="openrouter_api_key",
        input_price_per_m=input_price,
        output_price_per_m=output_price,
        tier=tier,
    )


def test_tier_rank_orders_fast_below_standard_below_smart():
    fast = _model("fast", id_="t-fast")
    standard = _model("standard", id_="t-standard")
    smart = _model("smart", id_="t-smart")
    max_tier = _model("max", id_="t-max")
    assert model_catalog.tier_rank(fast) < model_catalog.tier_rank(standard)
    assert model_catalog.tier_rank(standard) < model_catalog.tier_rank(smart)
    assert model_catalog.tier_rank(smart) < model_catalog.tier_rank(max_tier)


def test_price_sort_key_unpriced_fast_tier_beats_priced_smart_tier():
    """BUG FIX: an unpriced fast/standard-tier model used to get the same
    999.0 sentinel as an unpriced max-tier model, so it sorted as if it were
    the single most expensive option in the pool — behind even a real,
    known-expensive smart-tier price. A cheap-tier model with no catalog
    price yet should still rank ahead of an expensive priced one."""
    unpriced_fast = _model("fast", id_="unpriced-fast")
    priced_smart = _model("smart", input_price=50.0, output_price=100.0, id_="priced-smart")

    ranked = sorted([priced_smart, unpriced_fast], key=model_catalog.price_sort_key)

    assert [m.id for m in ranked] == ["unpriced-fast", "priced-smart"]


def test_price_sort_key_unpriced_max_tier_still_sorts_last():
    """Unlike fast/standard, an unpriced "max" tier model keeps the old
    worst-case sentinel — that tier is genuinely the priciest by design, so
    treating it as expensive-until-proven-otherwise is correct, not a bug."""
    unpriced_max = _model("max", id_="unpriced-max")
    priced_fast = _model("fast", input_price=0.1, output_price=0.2, id_="priced-fast")

    ranked = sorted([unpriced_max, priced_fast], key=model_catalog.price_sort_key)

    assert [m.id for m in ranked] == ["priced-fast", "unpriced-max"]


def test_validate_user_alias_allows_auto():
    model_catalog.validate_user_alias("auto", allow_auto=True)


def test_validate_user_alias_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown model alias"):
        model_catalog.validate_user_alias("not-a-model")


def test_user_update_rejects_unknown_default_model():
    with pytest.raises(ValidationError):
        UserUpdate(default_model="fake-model")


def test_user_update_accepts_model_mode():
    update = UserUpdate(default_model="auto")
    assert update.default_model == "auto"


def test_chat_create_accepts_auto():
    chat = ChatCreate(model="auto")
    assert chat.model == "auto"


def test_is_available_with_openrouter_key():
    settings = Settings(openrouter_api_key="sk-or-test", mock_llm_enabled=False)
    minimax = model_catalog.get("glm-5.2")
    assert model_catalog.is_available(minimax, settings) is True
    free = model_catalog.get("free-chat")
    assert model_catalog.is_available(free, settings) is True


def test_is_available_without_keys():
    settings = Settings(
        openrouter_api_key="",
        mock_llm_enabled=False,
    )
    minimax = model_catalog.get("glm-5.2")
    assert model_catalog.is_available(minimax, settings) is False


def test_speech_stt_alias_uses_direct_openai():
    stt = model_catalog.get("speech-stt-model")
    assert stt.model == "openai/gpt-4o-mini-transcribe"
    assert stt.api_key_field == "openai_api_key"
    assert model_catalog.openrouter_slug("speech-stt-model") == "openai/gpt-4o-mini-transcribe"
