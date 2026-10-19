"""Catalog of chat models — the single source of truth for routing, pricing,
provider, and availability. Adding a provider/model is one entry here.

Chat and image models route through **OpenRouter** using ``OPENROUTER_API_KEY``.
Voice uses OpenAI directly with ``OPENAI_API_KEY``.

Prices are USD per 1M tokens (approximate OpenRouter rates — update as needed).
A model is "available" when its configured key is set (or mock mode is on).

Product code uses ``id`` aliases only — never raw provider model strings outside
this file and ``litellm_gateway``.
"""

from dataclasses import dataclass

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
    # The OpenRouter reasoning sent at each level, from the model's own list of
    # supported efforts (GET /api/v1/models). An effort name is reasoning.effort;
    # "off" is reasoning.enabled false; None leaves the provider default. A
    # level a model does not list is never sent (asserted in tests).
    # Ordinary question: as little thinking as the model allows.
    thinking_off: str | None = None
    # A genuinely hard question: the cheapest level that still thinks.
    thinking_on: str | None = None
    # The user said the answer was wrong, or regenerated it: one level up.
    thinking_escalate: str | None = None
    # Hold the start of a reply until a stray closing think tag could have
    # arrived: GLM 5.3 has ended untagged reasoning with one.
    stray_think_guard: bool = False


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
    thinking_off: str | None = None,
    thinking_on: str | None = None,
    thinking_escalate: str | None = None,
    stray_think_guard: bool = False,
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
        thinking_off=thinking_off,
        thinking_on=thinking_on,
        thinking_escalate=thinking_escalate,
        stray_think_guard=stray_think_guard,
    )


CATALOG: tuple[ChatModel, ...] = (
    _or(
        id="free-chat",
        label="Claude Haiku 5.5",
        model="anthropic/claude-haiku-5.5",
        provider="anthropic",
        input_price_per_m=0.10,
        output_price_per_m=0.50,
        description="Fast, careful everyday answers and clear writing.",
        tier="fast",
        plan_access="free",
        thinking_off="none",
        thinking_on="low",
        thinking_escalate="medium",
    ),
    _or(
        id="smart-chat",
        label="DeepSeek V4.1 Flash",
        model="deepseek/deepseek-v4.1-flash",
        provider="deepseek",
        input_price_per_m=0.15,
        output_price_per_m=0.60,
        description="Strong reasoning for hard questions and code.",
        tier="smart",
        quota_multiplier=3.5,
        thinking_off="none",
        thinking_on="low",
        thinking_escalate="high",
    ),
    _or(
        id="glm-5.3-flash",
        label="GLM 5.3 Flash",
        model="z-ai/glm-5.3-flash",
        input_price_per_m=0.15,
        output_price_per_m=0.50,
        description="Quick step-by-step reasoning for maths and tricky questions.",
        tier="standard",
        plan_access="free",
        # Reasoning is mandatory here: OpenRouter answers a disable with a 400.
        stray_think_guard=True,
        thinking_off="low",
        thinking_on="low",
        thinking_escalate="high",
    ),
    _or(
        id="glm-5.2",
        label="GLM 5.2",
        model="z-ai/glm-5.2",
        input_price_per_m=0.62,
        output_price_per_m=2.42,
        description="Deep reasoning and coding; reads very long documents.",
        tier="smart",
        quota_multiplier=3.5,
        thinking_off="none",
        thinking_on="none",
        thinking_escalate="high",
    ),
    _or(
        id="gpt-6-luna",
        label="GPT-6 Luna",
        model="openai/gpt-6-luna",
        provider="openai",
        input_price_per_m=0.10,
        output_price_per_m=0.50,
        description="OpenAI's fast model for quick everyday answers.",
        tier="fast",
        thinking_off="none",
        thinking_on="low",
        thinking_escalate="medium",
    ),
    # The free plan's everyday model: about a third of Luna's price per turn,
    # as fast and as right on everyday turns, and it reads photos. Hard and
    # maths turns go to GLM 5.3 Flash, which it does not match without thinking.
    _or(
        id="qwen-3.7-flash",
        label="Qwen3.7 Flash",
        model="qwen/qwen3.7-flash",
        provider="qwen",
        input_price_per_m=0.03,
        output_price_per_m=0.13,
        description="Fast everyday answers; reads photos too.",
        tier="fast",
        plan_access="free",
        thinking_off="off",
        thinking_on="off",
        thinking_escalate="off",
    ),
    # Internal aliases — not user-selectable. Priced like the selectable entry
    # on the same model: the gateway adds their calls to the global spend.
    _or(
        id="title-model",
        label="Title",
        model="qwen/qwen3.7-flash",
        provider="qwen",
        input_price_per_m=0.03,
        output_price_per_m=0.13,
        selectable=False,
        thinking_off="off",
    ),
    _or(
        id="memory-model",
        label="Memory",
        model="qwen/qwen3.7-flash",
        provider="qwen",
        input_price_per_m=0.03,
        output_price_per_m=0.13,
        selectable=False,
        thinking_off="off",
    ),
    # Fallback for background LLM jobs (memory extraction, titles,
    # summaries). If the primary memory-model provider is down or slow, retry
    # once against a different provider so a single-provider outage doesn't
    # silently stall every background pipeline. Same OpenRouter transport.
    _or(
        id="fallback-memory-model",
        label="Memory (fallback)",
        model="anthropic/claude-haiku-5.5",
        provider="anthropic",
        input_price_per_m=0.10,
        output_price_per_m=0.50,
        selectable=False,
        thinking_off="none",
    ),
    _or(
        id="embedding-model",
        label="Embeddings",
        model="openai/text-embedding-3-small",
        provider="openai",
        input_price_per_m=0.02,
        output_price_per_m=0.0,
        selectable=False,
    ),
    # Qwen3.7 Flash reads photos at about a twentieth of Gemini 3.5 Flash-Lite's
    # output price; GLM 5.3 Flash below is the backup.
    _or(
        id="vision-chat",
        label="Vision",
        model="qwen/qwen3.7-flash",
        provider="qwen",
        input_price_per_m=0.03,
        output_price_per_m=0.13,
        selectable=False,
        thinking_off="off",
    ),
    # Second photo reader for when vision-chat's provider fails: another
    # company, and its reasoning cannot be disabled.
    _or(
        id="fallback-vision-model",
        label="Vision (fallback)",
        model="z-ai/glm-5.3-flash",
        input_price_per_m=0.15,
        output_price_per_m=0.50,
        selectable=False,
        thinking_off="low",
    ),
    _or(
        id="image-gen-model",
        label="Image generation",
        model="black-forest-labs/flux.2-klein-4b",
        provider="openrouter",
        selectable=False,
    ),
    ChatModel(
        id="speech-stt-model",
        label="Speech transcription",
        model="openai/gpt-4o-mini-transcribe",
        provider="openai",
        api_key_field="openai_api_key",
        selectable=False,
    ),
    ChatModel(
        id="speech-tts-model",
        label="OpenAI TTS",
        model="openai/gpt-4o-mini-tts",
        provider="openai",
        api_key_field="openai_api_key",
        selectable=False,
        description="OpenAI read-aloud.",
    ),
    ChatModel(
        id="speech-tts-fast-model",
        label="OpenAI TTS",
        model="openai/gpt-4o-mini-tts",
        provider="openai",
        api_key_field="openai_api_key",
        selectable=False,
        description="Legacy alias for OpenAI read-aloud.",
    ),
    ChatModel(
        id="live-talk-model",
        label="Live talk",
        model="openai/gpt-realtime-2.1",
        provider="openai",
        api_key_field="openai_api_key",
        selectable=False,
        description="Speech-to-speech for live talk.",
    ),
)

_BY_ID: dict[str, ChatModel] = {m.id: m for m in CATALOG}
_DEFAULT = _BY_ID["free-chat"]
# Qwen3.7 Flash answers an everyday turn as fast as GPT-6 Luna (about 0.8s to
# first text with thinking off) for about a third of the price. Auto's everyday
# lane carries most turns; hard and maths turns route stronger.
_AUTO_FAST = "qwen-3.7-flash"
_AUTO_SMART = "smart-chat"
# Live phone QA repeatedly saw DeepSeek R1 stream hidden reasoning and then
# return no visible answer. GLM 5.2 produced the verified worked-math contract
# in about two seconds, so Auto math uses this strong tier directly.
_AUTO_MATH = "glm-5.2"


def get(model_id: str) -> ChatModel:
    """Resolve a known product alias. Unknown ids raise — never silent fallback.

    Callers that intentionally want the default should use ``default_model()``
    or validate via ``known_ids()`` / ``validate_user_alias`` first.
    """
    try:
        return _BY_ID[model_id]
    except KeyError as exc:
        raise KeyError(f"Unknown model alias: {model_id!r}") from exc


def default_model() -> ChatModel:
    return _DEFAULT


def openrouter_slug(model_id: str) -> str:
    """Return the raw OpenRouter model id (no ``openrouter/`` prefix) for a
    product alias. Used by direct-HTTP gateways (speech, image generation)
    that talk to OpenRouter without going through LiteLLM.
    """
    model = get(model_id).model
    prefix = "openrouter/"
    return model[len(prefix) :] if model.startswith(prefix) else model


def known_ids() -> frozenset[str]:
    return frozenset(_BY_ID.keys())


def auto_fast_alias() -> str:
    return _AUTO_FAST


def auto_smart_alias() -> str:
    return _AUTO_SMART


def auto_math_alias() -> str:
    return _AUTO_MATH


def is_reasoning_alias(model_id: str) -> bool:
    """True for models that may think silently before the first token (R1, etc.)."""
    tier = get(model_id).tier
    return tier in {"smart", "max"}


def quota_multiplier(model_id: str) -> float:
    """Tokens charged against the daily quota (R1 and max tier cost more)."""
    return get(model_id).quota_multiplier


def estimate_cost_usd(
    model_id: str,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Estimated provider spend in USD from catalog prices and raw token counts.

    Returns ``None`` when the alias is unknown or both prices are unset (so
    callers can log "unknown" rather than silently recording 0).
    """
    try:
        model = get(model_id)
    except KeyError:
        return None
    if model.input_price_per_m is None and model.output_price_per_m is None:
        return None
    input_price = model.input_price_per_m or 0.0
    output_price = model.output_price_per_m or 0.0
    return (input_tokens / 1_000_000.0) * input_price + (output_tokens / 1_000_000.0) * output_price


def validate_user_alias(alias: str, *, allow_auto: bool = False) -> None:
    from app.core.validation import validate_user_alias as _validate

    _validate(alias, allow_auto=allow_auto)


# BUG FIX: a flat 999.0 for every model missing catalog pricing made
# unpriced fast/standard-tier entries (an open model with no list price — likely
# cheap, just not backfilled yet) sort as if they were the single most
# expensive option in the pool, behind even priced smart-tier models. Fall
# back to a per-tier estimate instead so an unpriced model lands among
# plausible peers by cost tier; "max" keeps the old worst-case sentinel
# since that tier is genuinely the priciest by design.
_TIER_PRICE_FALLBACK = {"fast": 0.5, "standard": 1.5, "smart": 5.0, "max": 999.0}
_DEFAULT_PRICE_FALLBACK = 999.0
_TIER_RANK = {"fast": 0, "standard": 1, "smart": 2, "max": 3}


def tier_rank(model: ChatModel) -> int:
    """Capability rank for Auto routing and chat fallbacks. Unknown → standard."""
    return _TIER_RANK.get(model.tier, 1)


def price_sort_key(model: ChatModel) -> tuple[float, float, str]:
    fallback = _TIER_PRICE_FALLBACK.get(model.tier, _DEFAULT_PRICE_FALLBACK)
    input_price = model.input_price_per_m if model.input_price_per_m is not None else fallback
    output_price = model.output_price_per_m if model.output_price_per_m is not None else fallback
    return (input_price, output_price, model.id)


def selectable_models() -> list[ChatModel]:
    return [m for m in CATALOG if m.selectable]
