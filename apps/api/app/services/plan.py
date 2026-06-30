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


def resolve_user_model_override(
    user: User,
    model_alias: str | None,
    content: str,
    settings: Settings,
) -> str:
    """Pick a concrete model, honoring a per-message override when allowed.

    A per-chat/per-message picker passes ``model_alias`` over the WS. Use it
    only if it's a concrete alias the user's plan allows; ``auto`` (or an
    alias not in the user's allowed pool) falls back to the Settings-based
    resolution so free users can't bypass plan gates.
    """
    if model_alias and model_alias != AUTO_ALIAS:
        if model_alias in allowed_model_ids(user, settings):
            return model_alias
    return resolve_user_model(user, content, settings)


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
