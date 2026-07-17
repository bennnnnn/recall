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
    """Map an OpenRouter model id to a LiteLLM model string.

    Always prefixes with ``openrouter/``. Slugs that already start with
    ``openrouter/`` (notably Auto Router ``openrouter/auto``) intentionally
    become ``openrouter/openrouter/...`` — that is LiteLLM's required form,
    not a double-prefix bug.
    """
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
    quota_multiplier: float = 1.0  # weight against daily token quota (R1 costs more)


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
    quota_multiplier: float = 1.0,
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
        quota_multiplier=quota_multiplier,
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
        quota_multiplier=3.5,
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
        model="z-ai/glm-4.7-flash",
        description="Zhipu GLM — fast multilingual model.",
        tier="standard",
        plan_access="free",
    ),
    _or(
        id="glm-5.2",
        label="GLM 5.2",
        model="z-ai/glm-5.2",
        input_price_per_m=0.93,
        output_price_per_m=2.92,
        description="Z.ai GLM — strong reasoning and coding (1M context).",
        tier="smart",
        quota_multiplier=3.5,
    ),
    _or(
        id="gpt-5.5",
        label="GPT 5.5",
        model="openai/gpt-5.5",
        provider="openai",
        input_price_per_m=5.00,
        output_price_per_m=30.00,
        description="OpenAI frontier — top reasoning, coding, and multimodal (1M context).",
        tier="smart",
        quota_multiplier=3.5,
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
        id="mercury-2",
        label="Mercury 2",
        model="inception/mercury-2",
        provider="inception",
        input_price_per_m=0.25,
        output_price_per_m=0.75,
        description="Ultra-fast diffusion LLM — lowest latency for everyday chat.",
        tier="fast",
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
        label="Max",
        model="openrouter/auto",
        description="OpenRouter picks the best model for each request.",
        tier="max",
        quota_multiplier=3.5,
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
    _or(
        id="image-gen-model",
        label="Image generation",
        model="black-forest-labs/flux.2-klein-4b",
        provider="openrouter",
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


def quota_multiplier(model_id: str) -> float:
    """Tokens charged against the daily quota (R1 and max tier cost more)."""
    return get(model_id).quota_multiplier


MODEL_MODES = frozenset({"auto"})


def validate_user_alias(alias: str, *, allow_auto: bool = False) -> None:
    from app.core.validation import validate_user_alias as _validate

    _validate(alias, allow_auto=allow_auto)


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
