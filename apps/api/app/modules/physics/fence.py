"""Physics-owned reconciliation of answer, trajectory, and simulation fences.

On a verified turn the model's own result fences are dropped, the solver's
card (marked ``verified: true``) lands under the reply's **Answer** heading in
place of the model's final line, and the scene is appended. A reply that answers
and then offers more ("Want the max height too?") keeps both; only a reply that
asks instead of stating any result goes without. A final value in the prose
that differs from the verified one gets one correction line above the card. An
Answer that gives the asked quantity another value keeps the card too when a
typed reader read the student's own words; a follow-up's rewrite or a photo's
reading leaves that Answer's value standing, unchecked.
"""

from __future__ import annotations

import json
import logging
import re

from app.modules.physics.part_answers import land_one_part_card, land_part_cards, parts_conflict
from app.modules.physics.schemas.simulation import SIMULATION_SPEC_TYPES
from app.modules.physics.sketches import without_model_drawings
from app.services.answer_check import asks_without_answering, correction_line, stated_verdict
from app.services.answer_fence import ANSWER_FENCE_LANGS, land_answer_card
from app.services.asked_value import asked_verdict
from app.services.closing_summary import closing_summary, with_closing_summary
from app.services.md_fence_scan import (
    block_end,
    close_unclosed_fences,
    iter_fences,
    strip_closed_fences,
)
from app.services.part.answer_cards import land_part_answer_cards, own_line_part_answers
from app.services.part.place import place_after_part
from app.services.solving import VerifiedPhysicsBlock
from app.services.subject_scan import scanner_camera_subject
from app.services.workout import as_formula_heading

logger = logging.getLogger(__name__)

_PICTURE_FENCE_LANGS = ("graph", "simulation", "geometry")
_DIAGRAM_FAILED = "*Could not render that diagram.*"
# "The diagram is drawn under this reply": where the app puts the picture, not the
# lesson's words (2026-10-30). The picture is simply below.
_DRAWN_UNDER_REPLY = re.compile(
    r"\b(is|are)\s+drawn\s+(?:under|below|beneath)\s+(?:this|the|my)\s+(?:reply|answer|message)",
    re.IGNORECASE,
)


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


def _scene_fences(verified: VerifiedPhysicsBlock) -> list[str]:
    """The solver's pictures: its sampled ```graph and ```simulation scenes."""
    fences: list[str] = []
    for spec in _canonical_specs(verified):
        spec_type = spec.get("type")
        if spec_type == "answer":
            continue
        fences.append(scene_fence(spec))
    return fences


def scene_fence(spec: dict[str, object]) -> str:
    """One picture's fence, as every physics picture is written: a scene or a diagram in
    ```simulation, a sampled curve in ```graph."""
    language = "simulation" if spec.get("type") in SIMULATION_SPEC_TYPES else "graph"
    return f"```{language}\n{json.dumps(spec, separators=(',', ':'))}\n```"


def scene_reply(verified: VerifiedPhysicsBlock) -> str | None:
    """ "Draw it" after a physics problem: the solver's pictures alone, or None with none."""
    fences = _scene_fences(verified)
    return "\n\n".join(fences) + "\n" if fences else None


def solver_cards(verified: VerifiedPhysicsBlock) -> tuple[str, ...]:
    """The fences physics writes for the block: its answer card (each part's, for a
    solve in parts) and its pictures, each part's own included."""
    answers = [part.display_answer for part in verified.physics_parts]
    if len(answers) < 2:
        answers = [(verified.display_answer or verified.canonical_answer or "").strip()]
    cards = [f"```answer\n{answer}\n```" for answer in answers if answer]
    # A part's own picture is the solver's too: kept, never dropped as a stranger (#2521).
    parts = [scene_fence(spec) for part in verified.physics_parts for spec in part.pictures]
    return (*cards, *dict.fromkeys([*_scene_fences(verified), *parts]))


# The unknown a law is solved for heads its formula, its subscript part of it: "h_{max}",
# "v_{impact}", "λ", "I". A v with no subscript is not v_i.
_UNKNOWN = re.compile(r"^\s*(\\?[A-Za-z]+(?:_\{(?:[^{}]|\{[^{}]*\})*\}|_[A-Za-z0-9])?)")


def _asked(verified: VerifiedPhysicsBlock) -> tuple[str, ...]:
    """The symbol the card answers."""
    head = _UNKNOWN.match(verified.physics_formulas[0]) if verified.physics_formulas else None
    return (head.group(1),) if head else ()


def validate_physics_fences(
    content: str,
    *,
    verified: VerifiedPhysicsBlock | None = None,
    correct: bool = True,
    user_text: str = "",
) -> str:
    """Drop model-authored result fences and append only solver-owned data.

    ``correct`` adds a correction line above the card when the prose states a
    different final value; the server never corrects its own (instant) text.
    ``user_text`` is the request: a flowchart it asked for survives the picture.
    """
    had_visual_fence = _has_picture_fence(content)
    # The model's card goes, and the sentence it closed on would be read as the answer: kept.
    summary = closing_summary(content)
    cleaned = own_line_part_answers(_without_model_result_fences(content))
    if verified is None:
        if had_visual_fence and not cleaned:
            return _DIAGRAM_FAILED
        return cleaned
    answer = (verified.display_answer or verified.canonical_answer or "").strip()
    # A question in parts: each part's card under its own Answer heading. A reply whose
    # part states another value is left as written, with no card claiming either.
    part_cards = [part.display_answer for part in verified.physics_parts]
    if len(part_cards) > 1 and parts_conflict(cleaned, part_cards):
        return cleaned
    by_part = land_part_cards(cleaned, part_cards)
    if by_part is None and answer and len(verified.physics_parts) < 2:
        by_part = land_one_part_card(cleaned, answer)
        # The parts the server did not solve get their own card, without the check.
        if by_part is not None:
            by_part = land_part_answer_cards(by_part) or by_part
    if by_part is not None:
        cleaned, answer = by_part, ""
    elif verified.partial:
        # The card answers one part of several: placed under the reply's one Answer it
        # would claim the whole question, and its "verified answer is" line would contradict
        # the other part's value (2026-11-04). Each part keeps the answer the reply gave.
        answer = ""
    # The law's own heading heads inputs, like **Formula**: its equations are no result.
    read = as_formula_heading(cleaned)
    if answer and _asks_instead_of_answering(read, answer):
        return cleaned
    held = asked_verdict(read, answer, _asked(verified)) if answer and correct else None
    if held == "conflict" and not read_from_their_words(verified, user_text):
        # The Answer gives the asked quantity one value, another than the card's, and the card
        # was read from a follow-up's rewrite or a photo: the two read the question differently
        # and the server's reading is the one in doubt, so the reply keeps its own value with
        # no check, and no scene of the server's reading.
        return land_answer_card(cleaned, None)
    if answer:
        # A typed reading of the student's own words stands: its card and scene, and a line
        # saying the verified value, over the model's other one (owner, 2026-11-13).
        conflict = correct and (
            held == "conflict" or (held is None and stated_verdict(read, answer) == "conflict")
        )
        # The summary comes back only when it says what the card says: "The kinetic energy is
        # 10 J." under a card of 9 J would contradict it (review, #2528).
        agrees = summary is not None and stated_verdict(summary, answer) != "conflict"
        cleaned = with_closing_summary(
            land_answer_card(cleaned, answer, above=correction_line(answer) if conflict else None),
            summary if agrees else None,
        )
    extras = _scene_fences(verified)
    own = [scene_fence(spec) for part in verified.physics_parts for spec in part.pictures]
    if not extras and not own:
        return cleaned
    text, placed = _part_pictures(without_model_drawings(cleaned, user_text), verified)
    rest = [fence for fence in dict.fromkeys([*extras, *own]) if fence not in placed]
    return _with_pictures(text, rest)


def _part_pictures(text: str, verified: VerifiedPhysicsBlock) -> tuple[str, list[str]]:
    """A question in parts: each picture of one part right after that part's card, never every
    part's picture together at the end (owner, 2026-11-21); and the pictures so placed. A
    picture several parts share (one projectile for its time, height and range) stays under
    them all."""
    if len(verified.physics_parts) < 2:
        return text, []
    owners: dict[str, list[str]] = {}
    for letter, part in zip("abcdefgh", verified.physics_parts, strict=False):
        for spec in part.pictures:
            owners.setdefault(scene_fence(spec), []).append(letter)
    placed: list[str] = []
    for fence, letters in owners.items():
        moved = place_after_part(text, letters[0], fence) if len(letters) == 1 else None
        if moved is not None:
            text, placed = moved, [*placed, fence]
    return text, placed


_SENTENCES = re.compile(r"(?<=[.?!])\s+")


def read_from_their_words(verified: VerifiedPhysicsBlock, user_text: str) -> bool:
    """The card is a typed reader's (an extractor, the binder, a chain of catalog laws) of the
    student's own words: every sentence it read is in their message. A follow-up's rewritten
    problem is not, and neither is a scanner photo's reading, which its caption carries."""
    read = verified.read_text
    if not read or verified.physics_intent is None or scanner_camera_subject(user_text):
        return False
    said = " ".join(user_text.split())
    return all(" ".join(sentence.split()) in said for sentence in _SENTENCES.split(read.strip()))


# "### Joke": a later request's section, after the one the solve answered.
_LATER_SECTION = re.compile(r"^#{2,3}\s+\S", re.MULTILINE)


def _with_pictures(text: str, pictures: list[str]) -> str:
    """The solve's pictures under its last answer card when another request's section
    follows it ("…, and also tell me a joke": the graph under the joke read as the
    joke's); otherwise at the end, as ever."""
    if pictures:
        text = _DRAWN_UNDER_REPLY.sub(r"\1 shown below", text)
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
