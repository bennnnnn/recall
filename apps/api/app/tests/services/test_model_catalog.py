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
