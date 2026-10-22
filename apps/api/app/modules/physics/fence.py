"""Physics-owned reconciliation of answer, trajectory, and simulation fences.

On a verified turn the model's own result fences are dropped, the solver's
card (marked ``verified: true``) lands under the reply's **Answer** heading in
place of the model's final line, and the scene is appended. A reply that answers
and then offers more ("Want the max height too?") keeps both; only a reply that
asks instead of stating any result goes without. A final value in the prose
that differs from the verified one gets one correction line above the card.
"""

from __future__ import annotations

import json
import logging
import re

from app.modules.physics.schemas.simulation import SIMULATION_SPEC_TYPES
from app.services.answer_check import asks_without_answering, correction_line, stated_verdict
from app.services.answer_fence import ANSWER_FENCE_LANGS, land_answer_card
from app.services.md_fence_scan import (
    block_end,
    close_unclosed_fences,
    iter_fences,
    strip_closed_fences,
)
from app.services.part_answers import land_part_cards
from app.services.solving import VerifiedPhysicsBlock
from app.services.workout import as_formula_heading

logger = logging.getLogger(__name__)

_PICTURE_FENCE_LANGS = ("graph", "simulation", "geometry")
_DIAGRAM_FAILED = "*Could not render that diagram.*"


def _has_picture_fence(content: str) -> bool:
    return any(fence.lang in _PICTURE_FENCE_LANGS for fence in iter_fences(content))


def _without_model_result_fences(content: str) -> str:
    """The prose: the model's own cards and pictures go; only the solver's ship."""
    for language in (*ANSWER_FENCE_LANGS, *_PICTURE_FENCE_LANGS):
        content = strip_closed_fences(content, language)
    return content.strip()


def _canonical_specs(verified: VerifiedPhysicsBlock) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for spec in (verified.canonical_fence, *verified.canonical_fences):
        if spec is not None and spec not in specs:
            specs.append(spec)
    return specs


def validate_physics_fences(
    content: str,
    *,
    verified: VerifiedPhysicsBlock | None = None,
    correct: bool = True,
) -> str:
    """Drop model-authored result fences and append only solver-owned data.

    ``correct`` adds a correction line above the card when the prose states a
    different final value; the server never corrects its own (instant) text.
    """
    had_visual_fence = _has_picture_fence(content)
    cleaned = _without_model_result_fences(content)
    if verified is None:
        if had_visual_fence and not cleaned:
            return _DIAGRAM_FAILED
        return cleaned
    extras: list[str] = []
    answer = (verified.display_answer or verified.canonical_answer or "").strip()
    # A question in parts: each part's card under its own Answer heading.
    by_part = land_part_cards(cleaned, [part.display_answer for part in verified.physics_parts])
    if by_part is not None:
        cleaned, answer = by_part, ""
    # The law's own heading heads inputs, like **Formula**: its equations are no result.
    read = as_formula_heading(cleaned)
    if answer and _asks_instead_of_answering(read, answer):
        return cleaned
    if answer:
        conflict = correct and stated_verdict(read, answer) == "conflict"
        cleaned = land_answer_card(
            cleaned, answer, above=correction_line(answer) if conflict else None
        )
    for spec in _canonical_specs(verified):
        spec_type = spec.get("type")
        if spec_type == "answer":
            continue
        language = "simulation" if spec_type in SIMULATION_SPEC_TYPES else "graph"
        extras.append(f"```{language}\n{json.dumps(spec, separators=(',', ':'))}\n```")
    return _with_pictures(cleaned, extras)


# "### Joke": a later request's section, after the one the solve answered.
_LATER_SECTION = re.compile(r"^#{2,3}\s+\S", re.MULTILINE)


def _with_pictures(text: str, pictures: list[str]) -> str:
    """The solve's pictures under its last answer card when another request's section
    follows it ("…, and also tell me a joke": the graph under the joke read as the
    joke's); otherwise at the end, as ever."""
    cards = [fence for fence in iter_fences(text) if fence.closed and fence.lang == "answer"]
    end = block_end(text, cards[-1]) if cards else -1
    if pictures and end >= 0 and _LATER_SECTION.search(text, end):
        return f"{text[:end]}\n\n" + "\n\n".join(pictures) + text[end:]
    return "\n\n".join(part for part in (text, *pictures) if part).strip()


def _asks_instead_of_answering(content: str, answer: str) -> bool:
    """A question and no result of its own: no card, no scene under it.

    Any stated final value, right or wrong, means the reply answered; a
    follow-up offer after it does not take the card away.
    """
    numeric = asks_without_answering(content, answer)
    if numeric is not None:
        return numeric
    if not any(line.rstrip("*_`~ \t").endswith("?") for line in content.splitlines()):
        return False
    normalized_content = re.sub(r"\s+", " ", content.lower())
    normalized_answer = re.sub(r"\s+", " ", answer.lower())
    return normalized_answer not in normalized_content


def replace_unclosed_physics_fences_safe(
    content: str,
    verified: VerifiedPhysicsBlock | None,
) -> str:
    """Physics-owned, no-solver fallback after finalization fails.

    Close a truncated rich fence, then make one ordinary canonical pass.  If
    even that fails, strip every physics/result fence and keep only prose;
    never send a physics turn through math's graph recovery semantics.
    """
    closed = close_unclosed_fences(content)
    try:
        return validate_physics_fences(closed, verified=verified)
    except Exception:
        logger.warning("physics fence finalization failed; keeping prose only", exc_info=True)
        cleaned = _without_model_result_fences(closed)
        return cleaned or (_DIAGRAM_FAILED if _has_picture_fence(closed) else "")
