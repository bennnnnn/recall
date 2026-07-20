import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.models.schemas import ChatCreate, UserUpdate
from app.services import model_catalog


def test_selectable_models_count():
    models = model_catalog.selectable_models()
    assert len(models) >= 7
    ids = {m.id for m in models}
    assert "free-chat" in ids
    assert "minimax-m2" in ids
    assert "mercury-2" in ids
    assert "glm-5.2" in ids
    mercury = model_catalog.get("mercury-2")
    assert mercury.tier == "fast"
    assert mercury.model == "openrouter/inception/mercury-2"
    glm = model_catalog.get("glm-5.2")
    assert glm.tier == "smart"
    assert glm.model == "openrouter/z-ai/glm-5.2"
    assert model_catalog.is_reasoning_alias("glm-5.2") is True
    gpt = model_catalog.get("gpt-5.5")
    assert gpt.tier == "smart"
    assert gpt.model == "openrouter/openai/gpt-5.5"
    assert gpt.input_price_per_m == 5.00
    assert gpt.output_price_per_m == 30.00
    assert model_catalog.is_reasoning_alias("gpt-5.5") is True
    assert "gpt-5.5" in {m.id for m in model_catalog.selectable_models()}


def test_known_model_aliases_match_catalog():
    from app.core.validation import KNOWN_MODEL_ALIASES

    assert KNOWN_MODEL_ALIASES == model_catalog.known_ids()


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
    minimax = model_catalog.get("minimax-m2")
    assert model_catalog.is_available(minimax, settings) is True
    free = model_catalog.get("free-chat")
    assert model_catalog.is_available(free, settings) is True


def test_is_available_without_keys():
    settings = Settings(
        openrouter_api_key="",
        mock_llm_enabled=False,
    )
    minimax = model_catalog.get("minimax-m2")
    assert model_catalog.is_available(minimax, settings) is False
