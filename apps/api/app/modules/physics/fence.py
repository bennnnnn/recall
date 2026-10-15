"""Physics-owned reconciliation of answer, trajectory, and simulation fences.

On a verified turn the model's own result fences are dropped and the solver's
card (marked ``verified: true``) and scene are appended. A reply that answers
and then offers more ("Want the max height too?") keeps both; only a reply that
asks instead of stating any result goes without. A final value in the prose
that differs from the verified one gets one correction line above the card.
"""

from __future__ import annotations

import json
import logging
import re

from app.modules.physics.schemas.simulation import SIMULATION_SPEC_TYPES
from app.services.answer_check import (
    asks_without_answering,
    correction_line,
    read_verified_value,
    stated_verdict,
)
from app.services.answer_fence import verified_answer_fence
from app.services.md_fence_scan import close_unclosed_fences, strip_closed_fences
from app.services.solving import VerifiedPhysicsBlock

logger = logging.getLogger(__name__)


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
    had_visual_fence = any(
        f"```{language}" in content for language in ("graph", "simulation", "geometry")
    )
    cleaned = content
    for language in ("answer", "result", "final", "graph", "simulation", "geometry"):
        cleaned = strip_closed_fences(cleaned, language)
    cleaned = cleaned.strip()
    if verified is None:
        if had_visual_fence and not cleaned:
            return "*Could not render that diagram.*"
        return cleaned
    extras: list[str] = []
    answer = (verified.display_answer or verified.canonical_answer or "").strip()
    if answer and _asks_instead_of_answering(cleaned, answer):
        return cleaned
    if answer:
        if correct and stated_verdict(cleaned, answer) == "conflict":
            extras.append(correction_line(answer))
        cleaned = _without_duplicated_answer(cleaned, answer)
        extras.append(verified_answer_fence(answer))
    for spec in _canonical_specs(verified):
        spec_type = spec.get("type")
        if spec_type == "answer":
            continue
        language = "simulation" if spec_type in SIMULATION_SPEC_TYPES else "graph"
        extras.append(f"```{language}\n{json.dumps(spec, separators=(',', ':'))}\n```")
    return "\n\n".join(part for part in (cleaned, *extras) if part).strip()


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


def _without_duplicated_answer(content: str, answer: str) -> str:
    """Drop a trailing Answer line that only repeats the verified fence.

    The direct card ends on the heading and keeps the number in the fence.
    A photo reply that writes the same number under Answer would show it twice.
    """
    match = re.search(
        r"(?P<head>(?:^|\n)[ \t]*(?:\*\*)?Answer(?:\*\*)?[ \t]*:?[ \t]*)"
        r"(?P<body>[^\n]*(?:\n[\s\S]*)?)?\Z",
        content,
        re.IGNORECASE,
    )
    if match is None or not match.group("body") or not match.group("body").strip():
        return content
    if not _restates(match.group("body"), answer):
        return content
    return content[: match.end("head")].rstrip()


def _restates(body: str, answer: str) -> bool:
    if _plain_answer(body) == _plain_answer(answer) and bool(_plain_answer(answer)):
        return True
    # "$R = 35.3\ \text{m}$" under Answer is the verified 35.3 m with its name.
    stated = read_verified_value(body.strip().strip("$").strip())
    verified = read_verified_value(answer)
    return (
        stated is not None
        and verified is not None
        and len(stated.numbers) == len(verified.numbers)
        and stated_verdict(body, answer) == "same"
    )


def _plain_answer(text: str) -> str:
    plain = re.sub(r"\\[a-zA-Z]+", " ", text)
    plain = plain.replace(r"\,", " ")
    plain = re.sub(r"[$\\{}_*`]", "", plain)
    return re.sub(r"\s+", " ", plain).strip(" .").lower()


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
        cleaned = closed
        had_visual = any(
            f"```{language}" in cleaned for language in ("graph", "simulation", "geometry")
        )
        for language in ("answer", "result", "final", "graph", "simulation", "geometry"):
            cleaned = strip_closed_fences(cleaned, language)
        cleaned = cleaned.strip()
        return cleaned or ("*Could not render that diagram.*" if had_visual else "")
