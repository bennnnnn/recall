"""One worked-solution layout for every subject.

A worked reply has the same sections everywhere, in this order, each only when
it has lines:

- **Given**: the problem as the student wrote it, or the stated values
- **Find**: what is asked
- **Formula**: the law or rule that governs it
- **Substitution**: values put into that formula
- **Steps**: an equation changed one move at a time
- **Answer**: the verified result (the caller's answer fence follows)

Each line is one state. A move is a short note after the state
(``$2x = 8$ — subtract 3 from both sides``), never a heading of its own.
Maths numbers each move instead (``modules/math/tools/lesson.py``): a bold
``**1. Subtract 4 from both sides**`` over the move written on both sides,
then the simplified line.
Lines in a section are hard line breaks, so the section reads as one block
and every client keeps the breaks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

GIVEN = "Given"
FIND = "Find"
FORMULA = "Formula"
SUBSTITUTION = "Substitution"
STEPS = "Steps"
ANSWER = "Answer"
WORKOUT_HEADINGS = (GIVEN, FIND, FORMULA, SUBSTITUTION, STEPS, ANSWER)

_NOTE_SEPARATOR = " — "
_HARD_BREAK = "  \n"


@dataclass(frozen=True)
class Workout:
    given: tuple[str, ...] = ()
    find: tuple[str, ...] = ()
    formula: tuple[str, ...] = ()
    substitution: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()


def math_line(tex: str, note: str | None = None) -> str:
    """``$2x = 8$ — subtract 3``: one state in math, its move as a short note."""
    body = f"${tex.strip()}$"
    return f"{body}{_NOTE_SEPARATOR}{note.strip()}" if note and note.strip() else body


def text_line(text: str, note: str | None = None) -> str:
    """A line that is not one formula (chemistry text, a named given)."""
    body = text.strip()
    return f"{body}{_NOTE_SEPARATOR}{note.strip()}" if note and note.strip() else body


# A law named for a person keeps its capital: "Newton's second law".
_PROPER_FIRST_WORD = re.compile(
    r"^(?:Pythagorean|Pythagoras|Newton|Ohm|Hooke|Boyle|Charles|Coulomb|Kepler|Snell|"
    r"Archimedes|Pascal|Bernoulli|Faraday|Avogadro|Bayes|Heron|Hess|Dalton|Graham|Henry|"
    r"Raoult|Nernst|Arrhenius|Beer|Gibbs|Hardy|Planck|Einstein|Lenz|Gauss|Kirchhoff|SUVAT)"
)


def note_from_label(label: str) -> str:
    """``Subtract 3 from both sides`` → ``subtract 3 from both sides``."""
    text = label.strip().rstrip(".:")
    if _PROPER_FIRST_WORD.match(text):
        return text
    if len(text) > 1 and text[0].isupper() and not text[1].isupper():
        return text[0].lower() + text[1:]
    return text


def formula_name(name: str) -> str:
    """A law's name as a note: ``Triangle area formula`` → ``Triangle area``."""
    text = name.strip().rstrip(".:")
    # "Heron's formula" is a name; "Triangle area formula" is a description.
    if not re.search(r"(?:'s|s')\s+formula$", text):
        text = text.removesuffix(" formula")
    return text[:1].upper() + text[1:]


def _clean(lines: tuple[str, ...]) -> list[str]:
    kept: list[str] = []
    for line in lines:
        text = re.sub(r"\s*\n\s*", " ", line).strip()
        if text and (not kept or kept[-1] != text):
            kept.append(text)
    return kept


def render_workout(
    workout: Workout,
    answer: str | None = None,
    *,
    before_answer: str | None = None,
) -> str:
    """The sections in order; with ``answer``, the answer fence closes it.

    ``before_answer`` is already-rendered markdown (numbered equation steps)
    placed after the sections and before **Answer**.
    """
    sections: list[str] = []
    for heading, lines in (
        (GIVEN, workout.given),
        (FIND, workout.find),
        (FORMULA, workout.formula),
        (SUBSTITUTION, workout.substitution),
        (STEPS, workout.steps),
    ):
        kept = _clean(lines)
        if kept:
            sections.append(f"**{heading}**{_HARD_BREAK}" + _HARD_BREAK.join(kept))
    if before_answer and before_answer.strip():
        sections.append(before_answer.strip())
    sections.append(f"**{ANSWER}**")
    body = "\n\n".join(sections)
    if answer is None:
        return body
    return f"{body}\n\n```answer\n{answer.strip()}\n```\n"


def split_equality_chain(tex: str) -> list[str]:
    """``a = b = c`` → ``["a = b", "= c"]``: one equals sign per line on a phone.

    Only top-level ``=`` split; one inside braces or ``\\left( … \\right)``
    belongs to a sub-expression.
    """
    if re.search(r"\\text|\\quad|\\;|,|<|>|\\(?:le|ge|ne)(?![a-z])", tex):
        # Two statements ("x = 2 or x = 3", "du = dx, v = e^x") are not a chain.
        return [tex]
    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    while i < len(tex):
        if tex.startswith("\\left", i):
            depth += 1
            i += 5
            continue
        if tex.startswith("\\right", i):
            depth -= 1
            i += 6
            continue
        char = tex[i]
        if char in "{(":
            depth += 1
        elif char in "})":
            depth -= 1
        elif char == "=" and depth == 0:
            parts.append(tex[start:i].strip())
            start = i + 1
        i += 1
    parts.append(tex[start:].strip())
    if len(parts) <= 2 or any(not part for part in parts):
        return [tex]
    return [f"{parts[0]} = {parts[1]}", *(f"= {part}" for part in parts[2:])]


_WORKOUT_SECTIONS = (
    "**Given** (the problem exactly as written, or the stated values), **Find** (what is "
    "asked), **Formula** (the governing law or rule, its name after an em dash), "
    "**Substitution** (values put into that formula)"
)
_WORKOUT_SECTION_LINES = (
    "Put each heading on its own line with its lines directly under it: one state per "
    "line, no blank line inside a section, one blank line between sections."
)
_WORKOUT_PARTS = (
    "A question in parts: one **Given** for the whole question, then for each part a bold "
    "label alone on its line naming its letter and what it finds (`**(a) Acceleration**`), "
    "followed by that part's **Formula**, **Substitution** and **Answer**, with no **Find** "
    "under a part; a later part may use an earlier part's answer as a given."
)
_WORKOUT_UNITS = (
    "Write units upright inside math (`$m = 5\\ \\text{kg}$`), never as italic letters "
    "(`$m = 5 kg$`)."
)
_WORKOUT_ONE_EXPRESSION = (
    "Trivial one-step arithmetic is one line with no headings. Write an expression once: "
    "`$\\frac{6!}{4!} = \\frac{720}{24}$`, then the result alone as the answer, never "
    "a second row that repeats the left side (`$\\frac{6!}{4!} = 30$`)."
)

# What the model is told for a physics or chemistry reply it writes itself.
WORKOUT_PROMPT_RULE = (
    "Worked-solution layout: bold headings in this order, each only when it has something "
    f"to show: {_WORKOUT_SECTIONS} or **Steps** (an equation changed one move at a time), "
    f"then **Answer**. {_WORKOUT_SECTION_LINES} Write a move as a short note after its "
    "line, e.g. `$2x = 8$ — subtract 3 from both sides`. No numbered steps, no separate "
    f"Simplify lines, no prose between lines. {_WORKOUT_PARTS} {_WORKOUT_UNITS} "
    f"{_WORKOUT_ONE_EXPRESSION}"
)

# What the model is told for a maths reply it writes itself: numbered moves, as the
# verified equation lesson renders them, so the phone draws each number as a badge.
MATH_WORKOUT_PROMPT_RULE = (
    "Worked-solution layout for maths: bold headings in this order, each only when it has "
    f"something to show: {_WORKOUT_SECTIONS} or numbered moves, then **Answer**. "
    f"{_WORKOUT_SECTION_LINES} Number every move in place of a **Steps** heading: a bold "
    "line naming the move (`**1. Subtract 4 from both sides**`), then its working, each "
    "`$...$` alone on its own line with no note after it. For an equation that working is "
    "the move written on both sides, then the simplified equation: `$4x + 4 - 4 = 0 - 4$`, "
    "then `$4x = -4$`; next `**2. Divide both sides by 4**`, "
    "`$\\frac{4x}{4} = \\frac{-4}{4}$`, then `$x = -1$`. A simplification is the last line "
    "of its move, never a number of its own. One blank line between numbered moves, no "
    f"prose between lines. {_WORKOUT_PARTS} {_WORKOUT_ONE_EXPRESSION}"
)

# The same rule in one sentence, for hints with a tight character budget.
WORKOUT_PROMPT_SHORT = (
    "Use the worked-solution layout: **Given**, **Find**, **Formula**, **Substitution** "
    "or **Steps**, **Answer**; one state per line, the move as a short note after it "
    "(`$2x = 8$ — subtract 3`); no numbered steps."
)

# Questions in parts and upright units, for a reply the model writes with no
# verified block to copy (the short rule above has no room for them).
WORKOUT_PARTS_PROMPT = f"{_WORKOUT_PARTS} {_WORKOUT_UNITS}"

# A reply the model works out itself has no server check behind it, so it checks
# its own answer before writing it, and shows that check when one line can.
SELF_CHECK_PROMPT_RULE = (
    "No server check stands behind this answer, so check it yourself before you write "
    "**Answer**: put the result back into the formula or the original equation, redo "
    "every multiplication and division, and check the units and that the size makes "
    "sense. If a check fails, fix the working first; never show a line you know is "
    "wrong. When one line can show the check, add **Check** after **Answer** with that "
    "line (`$2(8) + 5 = 21$`); otherwise leave it out. Never mark the check with ✓ and "
    "never call the result verified."
)
