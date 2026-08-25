"""Automatic model routing.

When a request uses the ``auto`` alias (or a user whose default model is
``auto``), pick a concrete model per message: cheap/fast for simple turns,
the stronger model for genuinely hard ones. Heuristic only — no extra LLM call.

Routing always respects the caller's allowed model pool (plan + enabled toggles).
"""

from __future__ import annotations

import re

from app.core.config import Settings
from app.services import model_catalog

# Hard triggers only — broad words like "why/explain" route too often to the
# strong model. "compare" alone is too broad (it fires on "compare these two
# files"), so comparison routing uses the explicit "X vs Y" / "versus" cues.
_SMART_TRIGGERS = (
    "prove ",
    "derive ",
    "debug ",
    "algorithm",
    "complexity",
    "architecture",
    "refactor",
    "trade-off",
    "tradeoff",
    "step by step",
    "design a system",
    "design a distributed",
    "optimize this",
    "big-o",
    "time complexity",
    "space complexity",
    # Comparison cues — "X vs Y" / "X versus Y" are genuinely hard and were
    # previously classifier-only web-search triggers with no model upgrade, so
    # a weak model answered a comparison with no SymPy/search help.
    " vs ",
    " versus ",
    # Bare coding asks without a code fence — "write a function/script/…"
    # stayed on the fast model because there was no ``` fence and no smart
    # keyword, so a hard coding question got a weak answer.
    "write a function",
    "write a script",
    "write a program",
    "write a method",
    "write a class",
    "write a regex",
    "write a snippet",
    "implement a",
    "implement the",
    "code a",
    "leetcode",
)

# Homework physics the verified solver does not cover (incline, momentum,
# escape velocity, …). needs_symbolic stays the solver gate so we don't
# inject fake verified fences; Auto still escalates so a weak model isn't
# left to invent F=ma on an incline. Bare "physics" must not match.
_PHYSICS_HOMEWORK_CUES = (
    "frictionless",
    "incline",
    "inclined plane",
    "momentum",
    "escape velocity",
    "centripetal",
    "simple harmonic",
    "coefficient of friction",
    "normal force",
    "pendulum",
    "projectile motion",
    "free body",
    "atwood",
)
# Formula / conceptual asks that are hard even without a printed number.
_PHYSICS_FORMULA_CUES = (
    "escape velocity",
    "simple harmonic",
    "pendulum",
    "atwood",
    "projectile motion",
)

_LONG_MESSAGE_CHARS = 800
# BUG FIX: this used to only match a fixed language allowlist
# (python/javascript/typescript/rust/go/java/c++/sql), so a bare ``` ```` ```
# fence with no language tag, or any other language (bash, shell, C, Kotlin,
# Swift, HTML, CSS, Ruby, PHP, ...), never escalated to the smart tier —
# real pasted code silently stayed on the cheap model. Match any fence
# opener (optionally followed by any language token) instead of an allowlist.
#
# SECURITY FIX (CodeQL: polynomial regex on uncontrolled data): the first
# version of this used `\s*` for the leading whitespace, which overlaps with
# what `(?:^|\n)` already matches on — a message that's mostly newlines with
# no closing fence (e.g. thousands of blank lines) let the engine retry the
# same run of `\n`s from every line-start position, going quadratic. `[ \t]*`
# can't consume `\n`, so each line's whitespace run is only ever scanned
# once — linear in input length regardless of how many blank lines it has.
_CODE_FENCE = re.compile(r"(?:^|\n)[ \t]*```")
# Bare "3+0" / "2 * 2" — no variable, not a word problem.
_BARE_ARITH = re.compile(
    r"^\s*-?\d+(?:\.\d+)?\s*[-+*/\u00d7\u00f7^]\s*-?\d+(?:\.\d+)?\s*[.?!]?\s*$"
)


def _looks_like_physics_homework(content: str) -> bool:
    """Hard physics asks the solver templates don't cover.

    Requires a quantity (a digit) for everyday words like "momentum", so
    "the project has momentum" stays on the fast model. Formula phrases
    (escape velocity, pendulum, …) escalate even without a number.
    """
    lower = content.lower()
    if not any(cue in lower for cue in _PHYSICS_HOMEWORK_CUES):
        return False
    if any(ch.isdigit() for ch in content):
        return True
    return any(cue in lower for cue in _PHYSICS_FORMULA_CUES)


def route_chat_model(content: str) -> str:
    """Return a preferred chat alias for an auto-routed message (before pool filter)."""
    text = content.lower()
    smart = model_catalog.auto_smart_alias()
    fast = model_catalog.auto_fast_alias()
    if len(content) >= _LONG_MESSAGE_CHARS:
        return smart
    if _CODE_FENCE.search(content):
        return smart
    if any(trigger in text for trigger in _SMART_TRIGGERS):
        return smart
    if _looks_like_physics_homework(content):
        return smart
    # Math / structured turns (equations, graphs, geometry, calculus, stats,
    # …) route to the smart model up front. A weak model on a math ask used to
    # produce wrong worked steps even with SymPy-verified fences injected, so
    # the verified answer and the prose disagreed. needs_symbolic is the same
    # gate the math pipeline uses, so routing and augmentation agree on what
    # "a math turn" is. Lazy import keeps routing import-time cheap.
    from app.services.math_text_match import needs_symbolic

    if needs_symbolic(content) and not _verified_math_stays_fast(content):
        return smart
    return fast


def _verified_math_stays_fast(content: str) -> bool:
    """SymPy already covers these; a reasoning model only writes a CoT essay.

    Keep equations / calculus / graphs on smart. Bare factorial ("4!") and
    "what is 1+1" style arithmetic stay on the fast model.
    """
    from app.services.math_text_match.discrete import combinatorics_signal
    from app.services.math_text_match.scan import has_algebraic_equation, prepare

    cleaned = prepare(content)
    if not cleaned:
        return False
    sig = combinatorics_signal(cleaned)
    if sig is not None and sig[0] == "factorial":
        return True
    if _BARE_ARITH.fullmatch(cleaned):
        return True
    lower = cleaned.lower()
    if "what is" not in lower or not any(ch.isdigit() for ch in cleaned):
        return False
    if not any(op in cleaned for op in ("+", "-", "*", "/", "\u00d7", "\u00f7", "^")):
        return False
    return not has_algebraic_equation(cleaned)


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
    del settings
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


def _pick_strongest_from_pool(pool: list[str]) -> str:
    """Best remaining model when the preferred smart/max alias is not in pool."""
    models = _models_in_pool(pool)
    if not models:
        return pool[0]
    models.sort(
        key=lambda m: (
            -model_catalog.tier_rank(m),
            -m.quota_multiplier,
            -model_catalog.price_sort_key(m)[0],
            -model_catalog.price_sort_key(m)[1],
            m.id,
        )
    )
    return models[0].id


def _pick_smart_from_pool(pool: list[str]) -> str:
    models = _models_in_pool(pool)
    smart = [m for m in models if m.tier in {"smart", "max"}]
    if smart:
        smart.sort(key=model_catalog.price_sort_key)
        return smart[0].id
    return _pick_strongest_from_pool(pool)


def _pick_preferred_tier(preferred: str, pool: list[str]) -> str:
    if preferred in pool:
        return preferred
    preferred_model = model_catalog.get(preferred)
    if preferred_model.tier in {"smart", "max"}:
        return _pick_smart_from_pool(pool)
    return _pick_fast_from_pool(pool)
