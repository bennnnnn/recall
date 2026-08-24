"""Subscription plan gates and per-user model pools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import Settings
from app.services import model_catalog, routing

if TYPE_CHECKING:
    from app.models.orm import User

AUTO_ALIAS = "auto"


def is_pro(user: User) -> bool:
    return user.plan == "pro"


def free_pool(settings: Settings) -> list[str]:
    """Cheapest models available on the free plan."""
    candidates = [
        m
        for m in model_catalog.selectable_models()
        if m.plan_access == "free" and model_catalog.is_available(m, settings)
    ]
    if not candidates:
        fallback = model_catalog.get(model_catalog.auto_fast_alias())
        if model_catalog.is_available(fallback, settings):
            return [fallback.id]
        return [model_catalog.auto_fast_alias()]
    candidates.sort(key=model_catalog.price_sort_key)
    return [m.id for m in candidates]


def default_pro_enabled(settings: Settings) -> list[str]:
    return [
        m.id for m in model_catalog.selectable_models() if model_catalog.is_available(m, settings)
    ]


def allowed_model_ids(user: User, settings: Settings) -> set[str]:
    if is_pro(user):
        return {
            m.id
            for m in model_catalog.selectable_models()
            if model_catalog.is_available(m, settings)
        }
    return set(free_pool(settings))


def is_auto_enabled(user: User) -> bool:
    if user.enabled_models is None:
        return True
    return AUTO_ALIAS in user.enabled_models


def model_pool(user: User, settings: Settings) -> list[str]:
    """Concrete model aliases Recall may use (never includes ``auto``)."""
    allowed = allowed_model_ids(user, settings)
    stored = user.enabled_models
    if stored:
        pool = [model_id for model_id in stored if model_id != AUTO_ALIAS and model_id in allowed]
        if pool:
            return pool
    if is_pro(user):
        enabled = [model_id for model_id in default_pro_enabled(settings) if model_id in allowed]
        return enabled or [model_catalog.auto_fast_alias()]
    return list(allowed) or [model_catalog.auto_fast_alias()]


def effective_enabled_models(user: User, settings: Settings) -> list[str]:
    """Alias for routing pool — kept for tests and callers."""
    return model_pool(user, settings)


def resolve_user_model(
    user: User,
    content: str,
    settings: Settings,
) -> str:
    """Pick a concrete model from the user's Settings preferences."""
    pool = model_pool(user, settings)
    if is_auto_enabled(user):
        return routing.resolve_alias_in_pool(AUTO_ALIAS, content, pool, settings)
    if len(pool) == 1:
        return pool[0]
    return routing.pick_cheapest_from_pool(pool, settings)


def _override_pool(user: User, settings: Settings) -> set[str]:
    """Models a per-message override may pick.

    This is ``model_pool`` (plan + the user's ``enabled_models`` preference),
    NOT ``allowed_model_ids`` (plan only): a model the user disabled in
    Settings must not be reachable via a WS/HTTP override even if their plan
    allows it. ``model_pool`` falls back to plan defaults when
    ``enabled_models`` is None, so default users keep the full plan pool.
    """
    return set(model_pool(user, settings))


def resolve_user_model_override(
    user: User,
    model_alias: str | None,
    content: str,
    settings: Settings,
) -> str:
    """Pick a concrete model, honoring a per-message override when allowed.

    A per-chat/per-message picker passes ``model_alias`` over the WS. Use it
    only if it's a concrete alias the user has enabled (and their plan allows);
    ``auto`` (or an alias not in the user's enabled pool) falls back to the
    Settings-based resolution so free users can't bypass plan gates and a
    disabled model can't be forced through the picker.

    L8: non-selectable aliases (not in ``_override_pool``) silently fall back
    to ``resolve_user_model`` rather than 400 — this is intentional: the
    mobile picker only sends selectable aliases, so an unknown value means
    a stale client / older app version, and failing would break their chat.
    """
    if model_alias and model_alias != AUTO_ALIAS:
        if model_alias in _override_pool(user, settings):
            return model_alias
    return resolve_user_model(user, content, settings)


def resolve_regenerate_model(
    user: User,
    model_alias: str | None,
    content: str,
    prior_assistant_model: str | None,
    settings: Settings,
) -> str:
    """Pick a model for a regenerate turn.

    Honors an explicit concrete override (a per-message picker pick) just like
    ``resolve_user_model_override``. When the picker is ``auto`` (or absent),
    reuse the model that produced the prior assistant reply so "try again"
    reproduces the same conditions instead of re-running the routing heuristic
    — a borderline query that auto-routed to a smart model the first time would
    otherwise re-route to a weaker model on regenerate. Falls back to routing
    if the prior model is unknown or no longer in the user's enabled pool.
    """
    pool = _override_pool(user, settings)
    if model_alias and model_alias != AUTO_ALIAS:
        if model_alias in pool:
            return model_alias
    if (
        prior_assistant_model
        and prior_assistant_model != AUTO_ALIAS
        and prior_assistant_model in pool
    ):
        return prior_assistant_model
    return resolve_user_model(user, content, settings)


def chat_fallback_models(
    user: User,
    settings: Settings,
    primary: str,
    *,
    max_fallbacks: int = 2,
    unhealthy: set[str] | None = None,
) -> list[str]:
    """Other models in the user's pool to try when the primary provider is down.

    ``unhealthy`` is a set of model aliases with poor health (high error rate
    or latency). When provided, unhealthy models are skipped so the fallback
    doesn't repeatedly hit a degraded provider.
    """
    if max_fallbacks <= 0:
        return []

    skip = unhealthy or set()
    allowed = allowed_model_ids(user, settings)
    candidates: list[str] = []

    # M11: memory_fallback_model_alias is for background jobs (memory/todo/
    # project extraction), not chat — it's non-selectable and never in
    # ``allowed``, so the check below was always false. Removed it so the
    # chat fallback pool is the user's other healthy selectable models,
    # ordered by tier proximity to the primary (not cheapest-first, which
    # failed a dead R1 over to the weakest fast model).
    for model_id in model_pool(user, settings):
        if model_id == primary or model_id in candidates:
            continue
        if model_id not in allowed:
            continue
        if model_id in skip:
            continue
        if model_catalog.is_available(model_catalog.get(model_id), settings):
            candidates.append(model_id)

    primary_rank = 0
    known = model_catalog.known_ids()
    if primary in known:
        primary_rank = model_catalog.tier_rank(model_catalog.get(primary))

    def _fallback_sort_key(model_id: str) -> tuple[int, tuple[float, float, str]]:
        model = model_catalog.get(model_id)
        return (
            abs(model_catalog.tier_rank(model) - primary_rank),
            model_catalog.price_sort_key(model),
        )

    candidates.sort(key=_fallback_sort_key)
    return candidates[:max_fallbacks]


def validate_enabled_models_for_update(
    user: User,
    enabled_models: list[str] | None,
    settings: Settings,
) -> list[str] | None:
    if enabled_models is None:
        return None
    allowed = allowed_model_ids(user, settings)
    cleaned: list[str] = []
    for item in enabled_models:
        if item == AUTO_ALIAS:
            if AUTO_ALIAS not in cleaned:
                cleaned.append(AUTO_ALIAS)
            continue
        if item in allowed and item not in cleaned:
            cleaned.append(item)
    has_auto = AUTO_ALIAS in cleaned
    model_ids = [item for item in cleaned if item != AUTO_ALIAS]
    if not has_auto and not model_ids:
        raise ValueError("Turn on Auto or at least one model.")
    return cleaned
