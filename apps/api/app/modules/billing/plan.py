"""Per-user model pools. Plan policy itself lives in ``entitlements``."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeGuard

from app.core.config import Settings
from app.exceptions import UnknownModelOverrideError
from app.modules.billing.entitlements import can_use, is_paid
from app.services import model_catalog, routing

if TYPE_CHECKING:
    from app.models.orm import User

__all__ = [
    "AUTO_ALIAS",
    "allowed_model_ids",
    "can_use",
    "chat_fallback_models",
    "default_pro_enabled",
    "free_pool",
    "image_turn_model",
    "is_auto_enabled",
    "is_explicit_pick",
    "is_paid",
    "model_pool",
    "resolve_regenerate_model",
    "resolve_user_model",
    "resolve_user_model_override",
    "validate_enabled_models_for_update",
]

AUTO_ALIAS = "auto"


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
    if can_use(user, "all_models", settings):
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
    if can_use(user, "all_models", settings):
        enabled = [model_id for model_id in default_pro_enabled(settings) if model_id in allowed]
        return enabled or [model_catalog.auto_fast_alias()]
    return list(allowed) or [model_catalog.auto_fast_alias()]


def resolve_user_model(
    user: User,
    content: str,
    settings: Settings,
    *,
    prior_user: str | None = None,
    prior_model: str | None = None,
    lesson_active: bool = False,
    unhealthy: frozenset[str] = frozenset(),
) -> str:
    """Pick a concrete model from the user's Settings preferences.

    Auto skips models whose provider is failing (``unhealthy``) while a healthy
    one is left in the pool.
    """
    pool = model_pool(user, settings)
    if is_auto_enabled(user):
        return routing.resolve_alias_in_pool(
            AUTO_ALIAS,
            content,
            pool,
            settings,
            prior_user=prior_user,
            prior_model=prior_model,
            lesson_active=lesson_active,
            unhealthy=unhealthy,
        )
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
    *,
    prior_user: str | None = None,
    prior_model: str | None = None,
    lesson_active: bool = False,
    unhealthy: frozenset[str] = frozenset(),
) -> str:
    """Pick a concrete model, honoring a per-message override when allowed.

    A per-chat/per-message picker passes ``model_alias`` over the WS. Use it
    only if it's a concrete alias the user has enabled (and their plan allows).
    ``auto`` and ``None`` route within the Settings pool. A concrete alias
    that is not in that pool raises rather than silently switching models.
    """
    if is_explicit_pick(model_alias):
        if model_alias not in _override_pool(user, settings):
            raise UnknownModelOverrideError(model_alias)
        return model_alias
    return resolve_user_model(
        user,
        content,
        settings,
        prior_user=prior_user,
        prior_model=prior_model,
        lesson_active=lesson_active,
        unhealthy=unhealthy,
    )


def is_explicit_pick(model_alias: str | None) -> TypeGuard[str]:
    """The picker named one model for this message (not Auto, not unset)."""
    return bool(model_alias) and model_alias != AUTO_ALIAS


def image_turn_model(
    user: User,
    settings: Settings,
    routed: str,
    *,
    explicit: bool,
    unhealthy: frozenset[str] = frozenset(),
) -> str:
    """The model for a turn that shows the model an image: one that can read it.

    An explicit pick that reads images keeps the turn. Auto's hard lanes take the
    strongest healthy image reader above the everyday tier in the user's pool, so
    a hard question about a photo still gets a model that thinks. Everything else
    goes to the photo lane (``model_catalog.vision_alias``).
    """
    vision = model_catalog.vision_alias()
    if explicit:
        return routed if model_catalog.reads_images(routed) else vision
    if routed == vision or routed not in model_catalog.known_ids():
        return vision
    everyday = model_catalog.tier_rank(model_catalog.get(model_catalog.auto_fast_alias()))
    if model_catalog.tier_rank(model_catalog.get(routed)) <= everyday:
        return vision
    readers = [
        model_id
        for model_id in model_pool(user, settings)
        if model_id not in unhealthy
        and model_catalog.reads_images(model_id)
        and model_catalog.tier_rank(model_catalog.get(model_id)) > everyday
    ]
    return routing.pick_strongest_from_pool(readers) if readers else vision


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
    if is_explicit_pick(model_alias):
        if model_alias not in pool:
            raise UnknownModelOverrideError(model_alias)
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
    unhealthy: set[str] | frozenset[str] | None = None,
    needs_vision: bool = False,
) -> list[str]:
    """Other models in the user's pool to try when the primary provider is down.

    ``unhealthy`` is a set of model aliases with poor health (high error rate
    or latency). When provided, unhealthy models are skipped so the fallback
    doesn't repeatedly hit a degraded provider. A model running the primary's
    own provider model is no backup. A turn that shows the model an image
    (``needs_vision``, or the photo lane as primary) falls back only to image
    readers, then to the photo lane's own backup.
    """
    if max_fallbacks <= 0:
        return []

    skip = unhealthy or set()
    known = model_catalog.known_ids()
    primary_model = model_catalog.get(primary) if primary in known else None
    needs_vision = needs_vision or primary == model_catalog.vision_alias()
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
        if model_id not in allowed or model_id in skip:
            continue
        model = model_catalog.get(model_id)
        if primary_model is not None and model.model == primary_model.model:
            continue
        if needs_vision and not model.supports_vision:
            continue
        if model_catalog.is_available(model, settings):
            candidates.append(model_id)

    primary_rank = model_catalog.tier_rank(primary_model) if primary_model is not None else 0

    def _fallback_sort_key(model_id: str) -> tuple[int, tuple[float, float, str]]:
        model = model_catalog.get(model_id)
        return (
            abs(model_catalog.tier_rank(model) - primary_rank),
            model_catalog.price_sort_key(model),
        )

    candidates.sort(key=_fallback_sort_key)
    if needs_vision:
        backup = model_catalog.get(model_catalog.vision_backup_alias())
        used = {model_catalog.get(model_id).model for model_id in candidates}
        if primary_model is not None:
            used.add(primary_model.model)
        if (
            backup.id not in skip
            and backup.model not in used
            and model_catalog.is_available(backup, settings)
        ):
            candidates.append(backup.id)
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
