"""Physics exercise selection and adjacent native-visual follow-ups.

Conversation text supplies a problem, never a scene or a trusted answer. Every
follow-up runs the problem through the physics solver again before rendering.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES, SimulationBlockSpec
from app.services.solving import VerifiedPhysicsBlock

# A closed request for one solved exercise. Extra topic/quantity requests must
# go through their own extraction instead of silently getting this example.
_EXERCISE = re.compile(
    r"(?:please\s+)?(?:do|solve|give(?:\s+me)?|show(?:\s+me)?)\s+"
    r"(?:one|a|an)\s+(?:10th\s+gr(?:a)?de|gr(?:a)?de\s+10|tenth\s+grade|class\s+10)\s+"
    r"physics\s+(?:problem|question|exercise)(?:\s+please)?[.!?]*",
    re.IGNORECASE,
)
_SCHOOL_PROBLEM = "A ball is thrown horizontally at 10 m/s from a height of 5 m. Find the range."
_VISUAL = re.compile(
    r"(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?"
    r"(?:(?:show|draw|render|give)(?:\s+me)?|i\s+(?:want|would\s+like))\s+"
    r"(?:a\s+|an\s+|the\s+)?(?:native\s+)?(?:diagram|animation|simulation|visual)"
    r"(?:\s+(?:of|for)\s+(?:it|this|that|the\s+problem))?(?:\s+please)?[.!?]*"
    r"|(?:please\s+)?(?:animate|draw|show|render)\s+(?:it|this|that)(?:\s+please)?[.!?]*"
    r"|(?:a\s+|an\s+)?(?:diagram|animation|simulation|visual)(?:\s+please)?[.!?]*"
    r"|(?:can|could|may)\s+i\s+(?:see|have)\s+(?:a|an|the)\s+"
    r"(?:diagram|animation|simulation|visual)(?:\s+please)?[.!?]*",
    re.IGNORECASE,
)
_ACCEPT = re.compile(
    r"(?:yes(?:\s+please)?|sure|go\s+ahead|i\s+want\s+one|i'd\s+like\s+one)[.!?]*",
    re.IGNORECASE,
)
_VISUAL_NOUN = r"(?:diagram|animation|simulation|visual(?:ization)?|sketch|plot|animated\s+version)"
_VISUAL_OBJECT = (
    r"(?:(?:a|an|the|my|you\s+a|you\s+an)\s+)?"
    r"(?:(?:native|verified|interactive|animated|simple|physics|free[- ]body|"
    r"velocity[-\u2013]time|position[-\u2013]time)\s+){0,3}" + _VISUAL_NOUN
)
_VISUAL_ACTION = (
    r"(?:animate(?:\s+(?:it|this|that|one))?|"
    r"(?:draw|render|show|create|make|provide|display|give|generate|sketch|plot|see)\s+"
    r"(?:you\s+)?(?:"
    r"(?:it|this|that|one)(?=\s*(?:[.!?;:]|$))|" + _VISUAL_OBJECT + r"))"
)
_OFFER = re.compile(
    r"\b(?:(?:would\s+you\s+like|do\s+you\s+want|want)\s+"
    r"(?:(?:me\s+)?to\s+)?(?:" + _VISUAL_OBJECT + "|" + _VISUAL_ACTION + r")|"
    r"(?:i(?:\s+(?:can|will|could)|['\u2019]ll)|shall\s+i)\s+"
    + _VISUAL_ACTION
    + r"|(?:would|could)\s+"
    + _VISUAL_OBJECT
    + r"\s+help|"
    r"let\s+me\s+know\s+if\s+you\s+(?:want|would\s+like)\s+" + _VISUAL_OBJECT + r")\b",
    re.IGNORECASE,
)
_DRAWING_CLAIM = re.compile(
    r"\b(?:here(?:\s+is|['\u2019]s)|below\s+is|i['\u2019]ve\s+(?:drawn|created))\s+"
    + _VISUAL_OBJECT
    + r"\b",
    re.IGNORECASE,
)
_PROBLEM = re.compile(r"\*\*Problem:?\*\*\s*\n+([^\n]+)(?:\n|$)", re.IGNORECASE)

VISUAL_UNAVAILABLE = "I can't render a verified native diagram for this problem yet."
ANIMATION_UNAVAILABLE = "I can't render a verified native animation for this problem yet."


@dataclass(frozen=True)
class PhysicsVisualFollowup:
    problem: str
    animation: bool


_OFFER_INTRO = re.compile(
    r"(?:would\s+you\s+like|let\s+me\s+know\s+if\s+you(?:['\u2019]d\s+like|\s+would\s+like|\s+want)):",
    re.IGNORECASE,
)


def _visual_offer(text: str) -> re.Match[str] | None:
    normalized = re.sub(r"(?m)^[ \t]*[-*\u2022]\s+", "", text)
    normalized = _OFFER_INTRO.sub("Would you like", normalized)
    return _OFFER.search(normalized)


def exercise_for_request(text: str) -> str | None:
    return _SCHOOL_PROBLEM if len(text) <= 200 and _EXERCISE.fullmatch(text.strip()) else None


def is_visual_request(text: str) -> bool:
    cleaned = re.sub(
        r"^(?:ok(?:ay)?|yes|sure|alright|great)[, ]+", "", text.strip(), flags=re.IGNORECASE
    )
    return len(text) <= 200 and _VISUAL.fullmatch(cleaned) is not None


def is_visual_acceptance(text: str) -> bool:
    return len(text) <= 100 and _ACCEPT.fullmatch(text.strip()) is not None


def physics_visual_followup(
    text: str, history: list[dict[str, str]]
) -> PhysicsVisualFollowup | None:
    """Read complete adjacent pairs, stopping at any unrelated exchange."""
    explicit = is_visual_request(text)
    if not explicit and not is_visual_acceptance(text):
        return None
    from app.modules.physics.extract import needs_physics

    # Multiple redraws may refer to the same problem, but never jump across an
    # unrelated user turn or use an orphaned assistant response as its source.
    pairs = [
        (row.get("role"), row.get("content", "")) for row in history if row.get("role") != "system"
    ]
    animation = bool(re.search(r"\banimat", text, re.IGNORECASE))
    for depth in range(4):
        if len(pairs) < 2 or pairs[-1][0] != "assistant" or pairs[-2][0] != "user":
            return None
        prior_user, assistant = pairs[-2][1], pairs[-1][1]
        offer = _visual_offer(assistant[-2_000:])
        if depth == 0 and not explicit:
            if offer is None:
                return None
            animation = bool(re.search(r"\banimat", offer.group(), re.IGNORECASE))
        selected = exercise_for_request(prior_user)
        if selected is not None or needs_physics(prior_user):
            # The previous answer may have been model-authored. Recover only
            # the statement of its exercise, then solve it again; discard all
            # its numbers in answer cards and all its drawing payloads.
            statement = _assistant_problem(assistant)
            problem = statement if statement is not None else prior_user
            return PhysicsVisualFollowup(problem, animation)
        if is_visual_acceptance(prior_user):
            if (
                len(pairs) < 4
                or pairs[-3][0] != "assistant"
                or not _visual_offer(pairs[-3][1][-2_000:])
            ):
                return None
        elif not is_visual_request(prior_user):
            return None
        pairs = pairs[:-2]
    return None


def _assistant_problem(assistant: str) -> str | None:
    from app.modules.physics.extract import extract_physics_intent

    statements = list(_PROBLEM.finditer(assistant[:4_000]))
    if len(statements) > 1:
        return ""  # Explicit ambiguity must not fall back to a different problem.
    if statements:
        return statements[0].group(1).strip()
    # Older provider replies sometimes used a plain paragraph for the
    # exercise. Admit one closed problem before any working, never an answer
    # card, a scene payload, or several different problems.
    head = assistant[:4_000].split("```", 1)[0]
    head = re.split(r"\*\*(?:Given|Find|Solution|Formula|Answer):?\*\*", head, maxsplit=1)[0]
    candidates = [
        paragraph.strip()
        for paragraph in head.split("\n\n")[:8]
        if len(paragraph) <= 1_000 and extract_physics_intent(paragraph) is not None
    ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1 or re.search(r"\b(?:another|new|next)\s+problem\b", head, re.IGNORECASE):
        return ""
    return None


def native_visual_specs(verified: VerifiedPhysicsBlock | None) -> list[dict[str, Any]]:
    """Admit only the native schema the mobile Skia renderer implements."""
    if verified is None:
        return []
    scenes: list[dict[str, Any]] = []
    for spec in (verified.canonical_fence, *verified.canonical_fences):
        if spec is None or spec.get("type") not in SIMULATION_SPEC_TYPES or spec in scenes:
            continue
        try:
            SimulationBlockSpec.model_validate(spec)
        except ValueError:
            continue
        scenes.append(spec)
    return scenes


def has_native_visual(verified: VerifiedPhysicsBlock | None, *, animation: bool = False) -> bool:
    scenes = native_visual_specs(verified)
    if not animation:
        return bool(scenes)
    return any(
        any(point != body["path"][0] for point in body["path"][1:])
        for scene in scenes
        for body in scene.get("bodies", [])
    )


def remove_visual_offers(text: str) -> str:
    """A prompt instruction alone cannot enforce the renderer's capability."""
    paragraphs = text.split("\n\n")
    kept: list[str] = []
    index = 0
    while index < len(paragraphs):
        paragraph = paragraphs[index]
        if _OFFER_INTRO.fullmatch(paragraph.strip()) and index + 1 < len(paragraphs):
            if _visual_offer(paragraph + "\n" + paragraphs[index + 1]):
                index += 2
                continue
        if any(
            _OFFER_INTRO.fullmatch(line.strip()) for line in paragraph.splitlines()
        ) and _visual_offer(paragraph):
            index += 1
            continue
        kept.append(paragraph)
        index += 1
    text = "\n\n".join(kept)
    lines: list[str] = []
    for line in text.split("\n"):
        if _OFFER.search(line) or _DRAWING_CLAIM.search(line):
            sentences = re.split(r"(?<=[.!?])\s+", line)
            line = " ".join(
                sentence
                for sentence in sentences
                if not _OFFER.search(sentence) and not _DRAWING_CLAIM.search(sentence)
            )
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def remove_text_art(text: str) -> str:
    """Drop indented and plain ASCII/Unicode diagram substitutes."""
    from app.services.md_fence_scan import strip_hand_sketch_filler

    paragraphs: list[str] = []
    for paragraph in strip_hand_sketch_filler(text).split("\n\n"):
        art_lines = sum(
            bool(re.fullmatch(r"[ +\-|/\\^v<>oO*.=┌┐└┘─│┬┴├┤\u2571╲→↓↑←]+", line.strip()))
            for line in paragraph.splitlines()
            if line.strip()
        )
        if art_lines < 2:
            paragraphs.append(paragraph)
    return "\n\n".join(paragraphs).strip()
