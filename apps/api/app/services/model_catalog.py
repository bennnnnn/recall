"""Catalog of chat models — the single source of truth for routing, pricing,
provider, and availability. Adding a provider/model is one entry here.

All models route through **OpenRouter** (one API key). LiteLLM talks to
``https://openrouter.ai/api/v1`` using ``OPENROUTER_API_KEY``.

Prices are USD per 1M tokens (approximate OpenRouter rates — update as needed).
A model is "available" when ``openrouter_api_key`` is set (or mock mode is on).

Product code uses ``id`` aliases only — never raw provider model strings outside
this file and ``litellm_gateway``.
"""

from dataclasses import dataclass

from app.core.config import Settings

OPENROUTER_KEY = "openrouter_api_key"


def litellm_openrouter_model(openrouter_slug: str) -> str:
    """LiteLLM expects ``openrouter/<openrouter-model-id>``."""
    if openrouter_slug.startswith("openrouter/"):
        return f"openrouter/{openrouter_slug}"
    return f"openrouter/{openrouter_slug}"


@dataclass(frozen=True)
class ChatModel:
    id: str  # product alias used everywhere in app/business code
    label: str
    provider: str
    model: str  # LiteLLM model string (openrouter/…)
    api_key_field: str  # Settings attribute holding the provider key
    api_base: str | None = None
    input_price_per_m: float | None = None  # USD / 1M input tokens (approx, configurable)
    output_price_per_m: float | None = None
    description: str = ""
    tier: str = "standard"  # fast | standard | smart | max — used by Auto routing
    plan_access: str = "pro"  # free | pro — free-plan users only see free-tier models
    selectable: bool = True  # shown in the model picker


def _or(
    *,
    id: str,
    label: str,
    model: str,
    provider: str = "openrouter",
    input_price_per_m: float | None = None,
    output_price_per_m: float | None = None,
    description: str = "",
    tier: str = "standard",
    plan_access: str = "pro",
    selectable: bool = True,
) -> ChatModel:
    """OpenRouter-backed catalog entry (``openrouter_slug`` = OpenRouter model id)."""
    return ChatModel(
        id=id,
        label=label,
        provider=provider,
        model=litellm_openrouter_model(model),
        api_key_field=OPENROUTER_KEY,
        api_base=None,
        input_price_per_m=input_price_per_m,
        output_price_per_m=output_price_per_m,
        description=description,
        tier=tier,
        plan_access=plan_access,
        selectable=selectable,
    )


CATALOG: tuple[ChatModel, ...] = (
    _or(
        id="free-chat",
        label="DeepSeek Chat",
        model="deepseek/deepseek-chat",
        provider="deepseek",
        input_price_per_m=0.14,
        output_price_per_m=0.28,
        description="Fast everyday chat — cheap and capable.",
        tier="fast",
        plan_access="free",
    ),
    _or(
        id="smart-chat",
        label="DeepSeek R1",
        model="deepseek/deepseek-r1",
        provider="deepseek",
        input_price_per_m=0.70,
        output_price_per_m=2.50,
        description="Stronger reasoning for hard questions and code.",
        tier="smart",
    ),
    _or(
        id="minimax-m2",
        label="Minimax M2",
        model="minimax/minimax-m2",
        description="Minimax flagship model.",
        tier="standard",
    ),
    _or(
        id="glm-4-flash",
        label="GLM-4 Flash",
        model="z-ai/glm-4.5-flash",
        description="Zhipu GLM — fast multilingual model.",
        tier="standard",
        plan_access="free",
    ),
    _or(
        id="qwen-plus",
        label="Qwen Plus",
        model="qwen/qwen-plus",
        description="Alibaba Qwen — strong general assistant.",
        tier="standard",
    ),
    _or(
        id="gemini-flash",
        label="Gemini 2.5 Flash",
        model="google/gemini-2.5-flash",
        description="Google Gemini — fast multimodal model.",
        tier="fast",
        plan_access="free",
    ),
    _or(
        id="llama-70b",
        label="Llama 3.3 70B",
        model="meta-llama/llama-3.3-70b-instruct",
        description="Meta Llama — open-weight instruct model.",
        tier="standard",
    ),
    _or(
        id="max-chat",
        label="OpenRouter Auto",
        model="openrouter/auto",
        description="OpenRouter picks the best model for each request.",
        tier="max",
    ),
    # Internal aliases — not user-selectable.
    _or(
        id="title-model",
        label="Title",
        model="deepseek/deepseek-chat",
        provider="deepseek",
        selectable=False,
    ),
    _or(
        id="memory-model",
        label="Memory",
        model="deepseek/deepseek-chat",
        provider="deepseek",
        selectable=False,
    ),
    # Fallback for background LLM jobs (memory/todo/project extraction, titles,
    # summaries). If the primary memory-model provider is down or slow, retry
    # once against a different provider so a single-provider outage doesn't
    # silently stall every background pipeline. Same OpenRouter transport.
    _or(
        id="fallback-memory-model",
        label="Memory (fallback)",
        model="qwen/qwen-plus",
        provider="qwen",
        selectable=False,
    ),
    _or(
        id="embedding-model",
        label="Embeddings",
        model="openai/text-embedding-3-small",
        provider="openai",
        selectable=False,
    ),
    _or(
        id="vision-chat",
        label="Vision",
        model="google/gemini-2.5-flash",
        provider="google",
        selectable=False,
    ),
)

_BY_ID: dict[str, ChatModel] = {m.id: m for m in CATALOG}
_DEFAULT = _BY_ID["free-chat"]
_AUTO_FAST = "free-chat"
_AUTO_SMART = "smart-chat"


def get(model_id: str) -> ChatModel:
    return _BY_ID.get(model_id, _DEFAULT)


def known_ids() -> frozenset[str]:
    return frozenset(_BY_ID.keys())


def auto_fast_alias() -> str:
    return _AUTO_FAST


def auto_smart_alias() -> str:
    return _AUTO_SMART


def is_reasoning_alias(model_id: str) -> bool:
    """True for models that may think silently before the first token (R1, etc.)."""
    tier = get(model_id).tier
    return tier in {"smart", "max"}


MODEL_MODES = frozenset({"auto"})


def validate_user_alias(alias: str, *, allow_auto: bool = False) -> None:
    if allow_auto and alias == "auto":
        return
    if alias in _BY_ID:
        return
    raise ValueError(f"Unknown model alias: {alias}")


def price_sort_key(model: ChatModel) -> tuple[float, float, str]:
    input_price = model.input_price_per_m if model.input_price_per_m is not None else 999.0
    output_price = model.output_price_per_m if model.output_price_per_m is not None else 999.0
    return (input_price, output_price, model.id)


def selectable_models() -> list[ChatModel]:
    return [m for m in CATALOG if m.selectable]


def is_available(model: ChatModel, settings: Settings) -> bool:
    from app.gateways import mock_llm

    if mock_llm.should_mock_llm(settings):
        return True
    return bool(getattr(settings, model.api_key_field, ""))
