"""Automatic model routing.

When a request uses the ``auto`` alias (or a user whose default model is
``auto``), pick a concrete model per message: cheap/fast for simple turns,
the stronger model for genuinely hard ones. Heuristic only — no extra LLM call.

Routing always respects the caller's allowed model pool (plan + enabled toggles).
"""

from __future__ import annotations

import re
from typing import Any

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

_FOLLOWUP_MAX_CHARS = 120
# Linear phrase scan — same style as prompt_constants.routing `_OFFER_PHRASES`.
# Do not add bare "fix" to `_SMART_TRIGGERS`; that would pin every "fix dinner"
# ask onto the strong model.
_FOLLOWUP_CUES = (
    "now fix",
    "fix it",
    "try again",
    "also",
    "instead",
    "the tests",
    "the error",
    "keep going",
    "make it",
    "change it",
    "do that",
)
_FOLLOWUP_LEAD_VERBS = frozenset(
    {
        "add",
        "fix",
        "retry",
        "patch",
        "update",
        "continue",
        "check",
        "verify",
        "handle",
        "review",
        "test",
    }
)
# Leading verb alone is not enough ("fix dinner", "add milk"). The rest of
# the line must refer to the prior task.
_FOLLOWUP_OBJECT_TOKENS = frozenset(
    {
        "it",
        "that",
        "this",
        "them",
        "these",
        "those",
        "tests",
        "test",
        "error",
        "errors",
        "bug",
        "bugs",
        "traceback",
        "types",
        "type",
        "handling",
        "handler",
        "patch",
        "retry",
        "retries",
        "function",
        "functions",
        "code",
        "timeout",
        "edge",
        "cases",
    }
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


def last_user_turn(messages: list[Any] | None) -> tuple[str | None, str | None]:
    """Last user line and the model stored on that row (oldest-first window).

    The current turn is not persisted yet. ``model`` is the alias resolved for
    that prior user turn — used so a chain of short follow-ups can keep Pro
    without re-scoring ``add tests`` in isolation.
    """
    if not messages:
        return None, None
    for msg in reversed(messages):
        if getattr(msg, "role", None) != "user":
            continue
        text = getattr(msg, "content", None)
        if not isinstance(text, str) or not text.strip():
            continue
        raw_model = getattr(msg, "model", None)
        model = raw_model.strip() if isinstance(raw_model, str) and raw_model.strip() else None
        return text, model
    return None, None


def last_user_content(messages: list[Any] | None) -> str | None:
    """Last user line already in the recent window (oldest-first)."""
    content, _ = last_user_turn(messages)
    return content


def _strip_followup_token(token: str) -> str:
    while token and token[0] in ".,!?;:'\"":
        token = token[1:]
    while token and token[-1] in ".,!?;:'\"":
        token = token[:-1]
    return token


def _alias_is_smart_tier(alias: str | None) -> bool:
    if not alias or alias not in model_catalog.known_ids():
        return False
    return model_catalog.get(alias).tier in {"smart", "max"}


def _prior_was_smart(prior_user: str, prior_model: str | None) -> bool:
    if _route_current_line(prior_user) == model_catalog.auto_smart_alias():
        return True
    return _alias_is_smart_tier(prior_model)


def _leading_followup_verb(lowered: str) -> bool:
    if not lowered or " " not in lowered:
        return False
    first, rest = lowered.split(" ", 1)
    while first and first[-1] in ".,!?;:":
        first = first[:-1]
    if first not in _FOLLOWUP_LEAD_VERBS:
        return False
    for raw in rest.split():
        if _strip_followup_token(raw) in _FOLLOWUP_OBJECT_TOKENS:
            return True
    return False


def _looks_like_smart_continuation(content: str) -> bool:
    """True when this line continues the prior hard turn, not a new topic."""
    from app.services.chat.prompt_constants.routing import (
        is_lightweight_chat_turn,
        is_personal_advice_question,
        is_short_confirmation,
        is_writing_deliverable_request,
    )
    from app.services.day_planning import is_day_planning_question
    from app.services.text_normalize import collapse_ws

    if is_personal_advice_question(content):
        return False
    if is_day_planning_question(content):
        return False
    if is_writing_deliverable_request(content):
        return False
    cleaned = collapse_ws(content)
    if len(cleaned) > _FOLLOWUP_MAX_CHARS:
        return False
    # yes / go / sure inherit; hi / thanks do not (those are lightweight acks).
    if is_short_confirmation(content):
        return True
    if is_lightweight_chat_turn(content):
        return False
    lowered = cleaned.lower()
    # Politeness should not change whether a task continuation inherits its tier.
    for prefix in ("please ", "can you ", "could you ", "would you "):
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix) :]
    if any(cue in lowered for cue in _FOLLOWUP_CUES):
        return True
    return _leading_followup_verb(lowered)


def _should_inherit_smart(
    content: str,
    prior_user: str,
    prior_model: str | None = None,
) -> bool:
    """Inherit Pro when the last user turn was (or stayed) on the smart tier."""
    if not _prior_was_smart(prior_user, prior_model):
        return False
    return _looks_like_smart_continuation(content)


def _route_current_line(content: str) -> str:
    """Score this message alone — no prior-turn inherit."""
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


def route_chat_model(
    content: str,
    *,
    prior_user: str | None = None,
    prior_model: str | None = None,
) -> str:
    """Return a preferred chat alias for an auto-routed message (before pool filter).

    Scores the current line first. A short continuation of a prior smart user
    turn inherits Pro; a new topic does not pin the rest of the chat.
    """
    smart = model_catalog.auto_smart_alias()
    preferred = _route_current_line(content)
    if preferred == smart:
        return smart
    if (
        prior_user
        and prior_user.strip()
        and _should_inherit_smart(content, prior_user, prior_model)
    ):
        return smart
    return preferred


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


def resolve_alias(
    alias: str,
    content: str,
    *,
    prior_user: str | None = None,
    prior_model: str | None = None,
) -> str:
    """Resolve ``auto`` / ``fast`` / ``smart`` without a pool (legacy/tests)."""
    all_ids = [m.id for m in model_catalog.selectable_models()]
    return resolve_alias_in_pool(
        alias, content, all_ids, prior_user=prior_user, prior_model=prior_model
    )


def resolve_alias_in_pool(
    alias: str,
    content: str,
    pool: list[str],
    settings: Settings | None = None,
    *,
    prior_user: str | None = None,
    prior_model: str | None = None,
) -> str:
    """Resolve a model mode or alias within an allowed pool."""
    if not pool:
        return model_catalog.auto_fast_alias()

    if alias == "auto":
        preferred = route_chat_model(content, prior_user=prior_user, prior_model=prior_model)
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
    smart = [m.id for m in models if m.tier in {"smart", "max"}]
    if smart:
        return _pick_strongest_from_pool(smart)
    return _pick_strongest_from_pool(pool)


def _pick_preferred_tier(preferred: str, pool: list[str]) -> str:
    if preferred in pool:
        return preferred
    preferred_model = model_catalog.get(preferred)
    if preferred_model.tier in {"smart", "max"}:
        return _pick_smart_from_pool(pool)
    return _pick_fast_from_pool(pool)
