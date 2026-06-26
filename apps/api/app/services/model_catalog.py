"""Catalog of chat models — the single source of truth for routing, pricing,
provider, and availability. Adding a provider/model is a one-line entry here.

Prices are USD per 1M tokens and are **configurable** — update them to match
your provider's current pricing. A model is "available" when its provider key is
configured (or when mock mode is on, since the app still responds via the mock).
"""

from dataclasses import dataclass

from app.core.config import Settings

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class ChatModel:
    id: str  # product alias used everywhere in app/business code
    label: str
    provider: str
    model: str  # litellm model string
    api_key_field: str  # Settings attribute holding the provider key
    api_base: str | None = None
    input_price_per_m: float | None = None  # USD / 1M input tokens (approx, configurable)
    output_price_per_m: float | None = None
    description: str = ""
    tier: str = "standard"
    selectable: bool = True  # shown in the model picker


CATALOG: tuple[ChatModel, ...] = (
    ChatModel(
        id="free-chat",
        label="Flash",
        provider="deepseek",
        model="deepseek/deepseek-chat",
        api_key_field="deepseek_api_key",
        input_price_per_m=0.14,
        output_price_per_m=0.28,
        description="",
        tier="fast",
    ),
    ChatModel(
        id="smart-chat",
        label="Pro",
        provider="deepseek",
        model="deepseek/deepseek-reasoner",
        api_key_field="deepseek_api_key",
        input_price_per_m=0.55,
        output_price_per_m=2.19,
        description="",
        tier="smart",
    ),
    ChatModel(
        id="max-chat",
        label="Max",
        provider="openrouter",
        # Adjust to any OpenRouter model id once you add an OpenRouter key.
        model="openrouter/auto",
        api_key_field="openrouter_api_key",
        api_base=OPENROUTER_API_BASE,
        description="",
        tier="max",
    ),
    # Internal aliases — not user-selectable.
    ChatModel(
        id="title-model",
        label="Title",
        provider="deepseek",
        model="deepseek/deepseek-chat",
        api_key_field="deepseek_api_key",
        selectable=False,
    ),
    ChatModel(
        id="memory-model",
        label="Memory",
        provider="deepseek",
        model="deepseek/deepseek-chat",
        api_key_field="deepseek_api_key",
        selectable=False,
    ),
)

_BY_ID: dict[str, ChatModel] = {m.id: m for m in CATALOG}
_DEFAULT = _BY_ID["free-chat"]


def get(model_id: str) -> ChatModel:
    return _BY_ID.get(model_id, _DEFAULT)


def selectable_models() -> list[ChatModel]:
    return [m for m in CATALOG if m.selectable]


def is_available(model: ChatModel, settings: Settings) -> bool:
    # In mock mode (no keys configured) the app still responds via the mock,
    # so treat every model as available for selection.
    from app.gateways import mock_llm

    if mock_llm.should_mock_llm(settings):
        return True
    return bool(getattr(settings, model.api_key_field, ""))
