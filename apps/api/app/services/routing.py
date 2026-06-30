"""Automatic model routing.

When a request uses the ``auto`` alias (or a user whose default model is
``auto``), pick a concrete model per message: cheap/fast for simple turns,
the stronger model for harder ones. Heuristic only — no extra LLM call.

Routing always respects the caller's allowed model pool (plan + enabled toggles).
"""

from __future__ import annotations

from app.core.config import Settings
from app.services import model_catalog

_SMART_TRIGGERS = (
    "explain",
    "why",
    "prove",
    "analyze",
    "analyse",
    "debug",
    "optimize",
    "optimise",
    "algorithm",
    "complexity",
    "architecture",
    "refactor",
    "trade-off",
    "tradeoff",
    "step by step",
    "reason",
    "derive",
    "compare",
    "evaluate",
    "design a",
)

_LONG_MESSAGE_CHARS = 500


def route_chat_model(content: str) -> str:
    """Return a preferred chat alias for an auto-routed message (before pool filter)."""
    text = content.lower()
    smart = model_catalog.auto_smart_alias()
    fast = model_catalog.auto_fast_alias()
    if len(content) >= _LONG_MESSAGE_CHARS:
        return smart
    if "```" in content:
        return smart
    if any(trigger in text for trigger in _SMART_TRIGGERS):
        return smart
    return fast


def resolve_alias(alias: str, content: str) -> str:
    """Resolve ``auto`` / ``fast`` / ``smart`` without a pool (legacy/tests)."""
    all_ids = [m.id for m in model_catalog.selectable_models()]
    return resolve_alias_in_pool(alias, content, all_ids)


def resolve_alias_in_pool(
    alias: str,
    content: str,
    pool: list[str],
    settings: Settings | None = None,
) -> str:
    """Resolve a model mode or alias within an allowed pool."""
    if not pool:
        return model_catalog.auto_fast_alias()

    if alias == "auto":
        preferred = route_chat_model(content)
        return _pick_preferred_tier(preferred, pool)

    if alias == "fast":
        return _pick_fast_from_pool(pool)

    if alias == "smart":
        return _pick_smart_from_pool(pool)

    if alias in pool:
        return alias

    return _pick_cheapest_from_pool(pool, settings)


def pick_cheapest_from_pool(pool: list[str], settings: Settings | None = None) -> str:
    return _pick_cheapest_from_pool(pool, settings)


def _models_in_pool(pool: list[str]) -> list[model_catalog.ChatModel]:
    known = model_catalog.known_ids()
    return [model_catalog.get(model_id) for model_id in pool if model_id in known]


def _pick_cheapest_from_pool(pool: list[str], settings: Settings | None) -> str:
    models = _models_in_pool(pool)
    if not models:
        return pool[0]
    models.sort(key=model_catalog.price_sort_key)
    return models[0].id


def _pick_fast_from_pool(pool: list[str]) -> str:
    models = _models_in_pool(pool)
    fast = [m for m in models if m.tier in {"fast", "standard"}]
    if fast:
        fast.sort(key=model_catalog.price_sort_key)
        return fast[0].id
    return _pick_cheapest_from_pool(pool, None)


def _pick_smart_from_pool(pool: list[str]) -> str:
    models = _models_in_pool(pool)
    smart = [m for m in models if m.tier in {"smart", "max"}]
    if smart:
        smart.sort(key=model_catalog.price_sort_key)
        return smart[0].id
    return _pick_cheapest_from_pool(pool, None)


def _pick_preferred_tier(preferred: str, pool: list[str]) -> str:
    if preferred in pool:
        return preferred
    preferred_model = model_catalog.get(preferred)
    if preferred_model.tier in {"smart", "max"}:
        return _pick_smart_from_pool(pool)
    return _pick_fast_from_pool(pool)
