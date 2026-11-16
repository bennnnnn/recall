"""The reply contract for a message that asks for more than one thing.

``turn_prep.intents`` decides what the requests are; this says how one reply answers
them all. Only a plan with two or more parts gets it: no other turn's prompt changes.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.turn_reading.plan import PartKind, TurnPart, TurnPlan
from app.services.picture_copy import PICTURE_PLACEMENT_RULE

MULTI_PART_MARKER = "This message asks for more than one thing."

# What the app does with a part itself; the reply only makes room for it.
_KIND_NOTES: dict[PartKind, str] = {
    "settings": (
        "a settings change. The app adds a card under your reply that applies it when "
        "tapped: do not say it is done, and do not explain how to change it. No section."
    ),
    "image": (
        "a picture to draw. The app adds it to your reply, or a line saying it could not: "
        "do not describe it, promise it, or write a prompt for it. No section."
    ),
    "photo": (
        "a real photo. Open the reply with a ```photo fence holding a short image search "
        "for it on one line (the app swaps it for a real photo); never describe the photo. "
        "No section."
    ),
    "reminder": (
        "a reminder. Handle it the way the To-do instructions say, in one short line; no section."
    ),
}
_NO_SECTION_KINDS: frozenset[PartKind] = frozenset({"settings", "image", "photo", "reminder"})
# The pictures a part may ask for.
_PICTURE_KINDS: frozenset[PartKind] = frozenset({"image", "photo"})
# A picture asked beside a problem a subject solves ("find the current and draw the
# circuit", "how far does it travel? Show the path."): the solve draws the problem's own
# picture, so no photo is looked up and nothing is painted (``chat.drawn_picture``).
PROBLEM_PICTURE_NOTE = (
    "a picture of the problem. The app draws it from the worked answer when it can: write "
    "no fence, prompt or sketch for it, and do not describe it or promise it. No section."
)

_SECTIONS = (
    "Put each request that needs a written answer under its own `###` heading of a few "
    "words naming it, in the order asked, with no intro before the first heading, and a "
    "line `---` between two sections. A calculation keeps its own working and its own "
    "Answer inside its section."
)
_ONE_ANSWER = "Only one of them needs a written answer: answer it directly, with no heading."
_RULES = (
    "Answer every request in this one reply. Give each the depth it needs: a longer or "
    "harder request must not crowd out a short one, and none may be skipped or folded "
    "into another. What the user said once (their situation, a place, a language, a "
    "level) applies to every request it fits. If one request is missing a detail that "
    "changes its answer, ask about it inside that request's section and still answer "
    "the others. Each request's length and layout are its own: a limit one sets does not "
    "apply to the others. Web results belong only to the request they answer."
)


def multi_part_contract(plan: TurnPlan, shapes: Sequence[Sequence[str]]) -> str:
    """The contract for ``plan``; ``shapes[i]`` is the layout hints request ``i`` asks for."""
    lines = [f"{MULTI_PART_MARKER} {len(plan.parts)} requests:"]
    for number, part in enumerate(plan.parts, start=1):
        note = _note(plan, part)
        lines.append(f'{number}. "{part.text}"' + (f": {note}" if note else ""))
    if plan.context:
        lines.append(f'Before asking they said: "{plan.context}".')
    answered = [part for part in plan.parts if part.kind not in _NO_SECTION_KINDS]
    lines.append(_SECTIONS if len(answered) > 1 else _ONE_ANSWER)
    lines.append(_RULES)
    if plan.of_kind(*_PICTURE_KINDS):
        lines.append(PICTURE_PLACEMENT_RULE)
    for number, hints in enumerate(shapes, start=1):
        lines.extend(f"For request {number} only: {hint}" for hint in hints)
    return "\n".join(lines)


def _note(plan: TurnPlan, part: TurnPart) -> str | None:
    """What the app does with ``part`` itself; a picture beside a solved problem is the
    solve's to draw."""
    if part.kind in _PICTURE_KINDS and plan.of_kind("solve"):
        return PROBLEM_PICTURE_NOTE
    return _KIND_NOTES.get(part.kind)
