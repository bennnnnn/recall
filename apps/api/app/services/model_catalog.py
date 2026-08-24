"""Service-facing model catalog compatibility API.

Pure catalog data and policy live in :mod:`app.models.model_catalog`; runtime
availability remains here because it depends on application settings and the
mock provider gateway.
"""

from app.core.config import Settings
from app.gateways import mock_llm
from app.models.model_catalog import (
    CATALOG,
    MODEL_MODES,
    ChatModel,
    auto_fast_alias,
    auto_smart_alias,
    default_model,
    estimate_cost_usd,
    get,
    is_reasoning_alias,
    known_ids,
    litellm_openrouter_model,
    openrouter_slug,
    price_sort_key,
    quota_multiplier,
    selectable_models,
    tier_rank,
    validate_user_alias,
)

__all__ = [
    "CATALOG",
    "MODEL_MODES",
    "ChatModel",
    "auto_fast_alias",
    "auto_smart_alias",
    "default_model",
    "estimate_cost_usd",
    "get",
    "is_available",
    "is_reasoning_alias",
    "known_ids",
    "litellm_openrouter_model",
    "openrouter_slug",
    "price_sort_key",
    "quota_multiplier",
    "selectable_models",
    "tier_rank",
    "validate_user_alias",
]


def is_available(model: ChatModel, settings: Settings) -> bool:
    if mock_llm.should_mock_llm(settings):
        return True
    return bool(getattr(settings, model.api_key_field, ""))
