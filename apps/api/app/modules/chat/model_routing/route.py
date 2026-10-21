"""Automatic model routing.

When a request uses the ``auto`` alias (or a user whose default model is
``auto``), pick a concrete model per message: cheap/fast for simple turns,
the stronger model for genuinely hard ones. Heuristic only — no extra LLM call.

Routing always respects the caller's allowed model pool (plan + enabled toggles).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import Settings
from app.models import model_catalog
from app.modules.billing.plan import (
    pick_cheapest_from_pool,
    pick_fast_from_pool,
    pick_preferred_tier,
    pick_smart_from_pool,
)
from app.modules.chat.model_routing.physics import physics_route
from app.modules.chat.model_routing.signals import SMART_TRIGGERS, needs_strong_model

logger = logging.getLogger(__name__)

_FOLLOWUP_MAX_CHARS = 120
# Linear phrase scan — same style as prompt_constants.routing `_OFFER_PHRASES`.
# Do not add bare "fix" to `SMART_TRIGGERS`; that would pin every "fix dinner"
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
    "next step",
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
    if _alias_is_smart_tier(_route_current_line(prior_user)):
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
    from app.modules.chat.continuation_subject import is_pure_continuation
    from app.modules.chat.prompt_constants.routing import (
        is_lightweight_chat_turn,
        is_personal_advice_question,
        is_short_confirmation,
    )
    from app.modules.chat.prompt_constants.writing_kind import is_writing_deliverable_request
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
    lowered = cleaned.lower().rstrip(" .,!?:;")
    if is_pure_continuation(content):
        return True
    # These are lightweight as standalone chat, but after a hard answer they
    # explicitly ask for its reasoning. Keep them on the same strong lane.
    if lowered in {"how", "how so", "why", "why not", "show me how", "explain how"}:
        return True
    # A learner normally names the exact disputed step after the question
    # word ("why is x=-1 rejected?", "how did you factor that?"). Requiring
    # the whole message to equal bare ``why``/``how`` dropped these natural
    # follow-ups onto the lightweight lane.
    if lowered.startswith(("why ", "how ")):
        return True
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


def _route_current_line(content: str, settings: Settings | None = None) -> str:
    """Score this message alone — no prior-turn inherit."""
    text = content.lower()
    smart = model_catalog.auto_smart_alias()
    fast = model_catalog.auto_fast_alias()
    if len(content) >= _LONG_MESSAGE_CHARS:
        return smart
    if _CODE_FENCE.search(content):
        return smart
    # Tutoring is structured by a strict prompt contract and is latency-sensitive:
    # a learner should not wait on a silent reasoning model before every small
    # step. The fast lane (then Gemini Flash) followed the lesson contract in
    # live QA at a fraction of the TTFT, so keep this classifier shared with the
    # prompt layer and use the fast lane. Hard coding/math still reaches the
    # smart checks below when it is not an explicit tutor/roadmap request.
    from app.modules.chat.prompt_constants.teaching import (
        is_learning_plan_request,
        is_teaching_request,
    )

    if is_learning_plan_request(content) or is_teaching_request(content):
        return fast
    # A request whose task is to *format* a small example as a Markdown table
    # is not a deep architecture/trade-off analysis. The column label
    # "Main tradeoff" previously tripped the generic smart cue and sent this
    # UI/layout stress case to R1, which could sit silent for tens of seconds.
    if "markdown table" in text and any(
        cue in text for cue in ("create ", "show ", "give me ", "make ")
    ):
        return fast
    if any(trigger in text for trigger in SMART_TRIGGERS):
        return smart
    from app.modules.chat.prompt_constants.writing_kind import is_writing_deliverable_request

    # A tweet or an email about a migration is writing, not the migration.
    if needs_strong_model(content) and not is_writing_deliverable_request(content):
        return smart
    from app.services.subject_solving import detect_subject

    # The lane follows the subject whose solver answers the line (code-health audit
    # DUP-05): a balanced equation or a molarity is chemistry's card, not the maths
    # lane's algebra, and a curve's maximum is maths' though it cues physics.
    chemistry_enabled = settings is None or settings.chemistry_enabled
    subject = detect_subject(content, chemistry_enabled=chemistry_enabled)
    if subject == "chemistry":
        return fast
    if subject != "math":
        physics_alias = physics_route(content, fast=fast, smart=smart, settings=settings)
        if physics_alias is not None:
            return physics_alias
    # Math turns (equations, graphs, geometry, calculus, stats, …) go to the math-tuned
    # strong model: a fast model's steps disagreed with the verified answer.
    from app.modules.chat.model_routing.rate_problems import is_multi_step_rate_problem

    if is_multi_step_rate_problem(content):  # catch-up, meet, together: the maths lane won't think
        return smart
    if subject == "math" and not _verified_math_stays_fast(content):
        return model_catalog.auto_math_alias()
    return fast


def route_chat_model(
    content: str,
    *,
    prior_user: str | None = None,
    prior_model: str | None = None,
    lesson_active: bool = False,
    settings: Settings | None = None,
) -> str:
    """Preferred chat alias for an auto-routed message (before pool filter).

    Lessons stay on the low-latency tier. "That's wrong" after an answer goes to
    the thinking tier; otherwise a short continuation of a smart turn inherits it.
    """
    from app.modules.chat.model_routing.thinking import is_answer_dispute

    smart = model_catalog.auto_smart_alias()
    if lesson_active:
        return model_catalog.auto_fast_alias()
    if prior_user and is_answer_dispute(content):
        return smart
    preferred = _route_current_line(content, settings)
    if preferred == smart:
        return smart
    if (
        prior_user
        and prior_user.strip()
        and _should_inherit_smart(content, prior_user, prior_model)
    ):
        math = model_catalog.auto_math_alias()
        if prior_model == math or _route_current_line(prior_user, settings) == math:
            return math
        return smart
    return preferred


def message_needs_thinking(
    content: str,
    *,
    prior_user: str | None = None,
    prior_model: str | None = None,
    lesson_active: bool = False,
    settings: Settings | None = None,
) -> bool:
    """True only when this job should spend a reasoning pass.

    The same split Auto uses for the strong lane, except the math lane:
    an equation still uses a strong model, and it does not think first.
    """
    return (
        route_chat_model(
            content,
            prior_user=prior_user,
            prior_model=prior_model,
            lesson_active=lesson_active,
            settings=settings,
        )
        == model_catalog.auto_smart_alias()
    )


def _verified_math_stays_fast(content: str) -> bool:
    """SymPy already covers these; a reasoning model only writes a CoT essay.

    Keep equations / calculus / graphs on smart. Bare factorial ("4!") and
    "what is 1+1" style arithmetic stay on the fast model.
    """
    from app.modules.math.match import (
        bare_arithmetic_expr,
        combinatorics_signal,
        prepare,
        written_arithmetic_request,
    )

    cleaned = prepare(content)
    if not cleaned:
        return False
    sig = combinatorics_signal(cleaned)
    if sig is not None and sig[0] == "factorial":
        return True
    # Same whole-message helper as the SymPy gate — a lone "1+1" inside a
    # harder question must not keep the turn on the fast model.
    return (
        bare_arithmetic_expr(cleaned) is not None or written_arithmetic_request(cleaned) is not None
    )


_MODES = frozenset({"auto", "fast", "smart"})


def resolve_alias_in_pool(
    alias: str,
    content: str,
    pool: list[str],
    settings: Settings | None = None,
    *,
    prior_user: str | None = None,
    prior_model: str | None = None,
    lesson_active: bool = False,
    unhealthy: frozenset[str] = frozenset(),
) -> str:
    """Resolve a model mode or alias within an allowed pool.

    A concrete alias is the user's pick and passes through. A mode (auto, fast,
    smart) chooses among the pool's healthy models, and for a JSON ask among those
    with JSON mode (``_usable_pool``).
    """
    if not pool:
        return model_catalog.auto_fast_alias()
    if alias not in _MODES:
        return alias if alias in pool else pick_cheapest_from_pool(pool, settings)
    usable = _usable_pool(pool, unhealthy, content)
    if alias == "fast":
        return pick_fast_from_pool(usable)
    if alias == "smart":
        return pick_smart_from_pool(usable)
    preferred = route_chat_model(
        content,
        prior_user=prior_user,
        prior_model=prior_model,
        lesson_active=lesson_active,
        settings=settings,
    )
    return pick_preferred_tier(preferred, usable)


def _usable_pool(pool: list[str], unhealthy: frozenset[str], content: str) -> list[str]:
    """The pool without unhealthy models; for a JSON ask, only models with JSON mode.

    Each filter applies only while it leaves a model: a degraded model beats none.
    """
    from app.modules.chat.json_output import is_json_request

    usable = [model_id for model_id in pool if model_id not in unhealthy] or pool
    if not is_json_request(content):
        return usable
    known = model_catalog.known_ids()
    with_json = [m for m in usable if m in known and model_catalog.get(m).json_mode]
    return with_json or usable
