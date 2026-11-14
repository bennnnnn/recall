"""Which of a reply's answer cards the server's one verified value may check.

A verified card read from words that the reply's own result contradicts gets no check. The
model is shown the server's result before it writes. When it still works a question in words
to another value, the two read the question differently, and the server's reading of words is
the one in doubt: "a jacket costs 2400 shillings, 15% off, then 16% VAT" was read as a
proportion and carried a checked 0.1 under working that ended at 2366.40 (2026-11-06). The
reply then stands as the model wrote it, its own final value in a card with no check, and the
pictures of the server's reading go with it. A card that names its quantity (an area, a
perimeter) is held to the one value the Answer writes against that quantity
(``services/asked_value.py``), as physics and chemistry hold theirs: the quarter circle's
Answer, A = 50.24 cm², stood under a checked ≈ 201.06 that no reading saw as a number
(2026-11-13). An expression in letters under a number contradicts it too. An equation or
expression the user typed is read without doubt, so a reply that solves it to another value
still gets the verified card and its correction line.

One verified value checks one card. A reply in parts with a card per part ("c = 15 cm",
"A = 54 cm²", "P = 36 cm") had every card rewritten to the one verified value, 36 three times:
only the card that states that value gets it, and each other part keeps its own, unchecked.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.services.answer_check import Verdict, stated_verdict
from app.services.answer_fence import (
    ANSWER_FENCE_LANGS,
    UNCHECKED_ANSWER_MARKER,
    answer_fence_value,
    answer_heading,
    demote_answer_body,
    demote_answer_fences,
    land_answer_card,
    normalize_owned_fences,
    verified_answer_fence,
)
from app.services.asked_value import QUANTITY_NAMES, asked_verdict
from app.services.card_text import card_maths
from app.services.md_fence_scan import iter_fences, map_closed_fences, strip_closed_fences

if TYPE_CHECKING:
    from app.modules.math.tools import VerifiedMathBlock

# The pictures a reading draws; the model's own copies are unchecked too.
_PICTURE_LANGS = ("graph", "geometry", "arithmetic", "simulation")


def _unchecked(body: str) -> str:
    return f"```answer\n{UNCHECKED_ANSWER_MARKER}\n{card_maths(answer_fence_value(body))}\n```\n"


def contradicted_reading(
    reply: str, verified: VerifiedMathBlock | None, answer_body: str | None
) -> str | None:
    """The reply with its own value in an unchecked card when the server read a question in
    words and the reply's own value (its answer card counts) contradicts the verified one;
    None otherwise."""
    if verified is None or not verified.read_from_words or not answer_body:
        return None
    worked = demote_answer_fences(reply)
    # Each value of a card of several held to its own name; else the one value the Answer
    # writes for the asked quantity; main's reading when there is no such one value
    # (several, another subscript, no Answer heading).
    verdict = (
        _per_part_verdict(worked, answer_body)
        or asked_verdict(worked, answer_body, verified.asked)
        or stated_verdict(worked, answer_body)
    )
    # A card no plain value (a ratio) may still face an Answer that is an expression in letters.
    letters = verdict == "unknown" and _letters_for_a_number(worked, answer_body)
    if verdict != "conflict" and not letters:
        return None
    text = normalize_owned_fences(reply, ANSWER_FENCE_LANGS)
    for lang in ANSWER_FENCE_LANGS:
        text = map_closed_fences(text, lang, _unchecked)
    for lang in _PICTURE_LANGS:
        text = strip_closed_fences(text, lang)
    return land_answer_card(text.strip(), None)


_CARD_PARTS = re.compile(r",\s*\\quad\s*")
_PART_VALUE = re.compile(r"\s*(?:=|\\approx)\s*")
_ARGUMENTS = re.compile(r"\([^()]*\)$")
_PART_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
# A measure's symbol and the words a reply names it by ("C": "circumference").
_PART_WORDS: dict[str, tuple[str, ...]] = {}
for _names in QUANTITY_NAMES.values():
    _PART_WORDS[_names[0]] = (*_PART_WORDS.get(_names[0], ()), *_names[1:])


def _per_part_verdict(worked: str, answer_body: str) -> Verdict | None:
    """A card of several named values ("C ≈ 18.85, A ≈ 28.27", "gcd(252, 198) = 18, lcm
    = 2772"): each value held to the one the Answer writes against its own name.
    "conflict" when one differs, "same" when each agrees, None when the card is one value
    or a part is not named in the Answer. A whole card held to the reply's last value
    demoted a complete correct gcd-and-lcm reply (2026-11-13 audit, MATH-04)."""
    parts = _CARD_PARTS.split(answer_fence_value(answer_body))
    if len(parts) < 2:
        return None
    verdicts: list[Verdict | None] = []
    for part in parts:
        pieces = _PART_VALUE.split(part.strip(), maxsplit=1)
        if len(pieces) != 2:
            return None
        name, value = pieces
        bare = _ARGUMENTS.sub("", name).strip().lstrip("\\")
        bare = re.sub(r"^operatorname\{(\w+)\}$", r"\1", bare)
        names = tuple(dict.fromkeys((bare, name.strip(), *_PART_WORDS.get(bare, ()))))
        # The number alone: "28.27 units²" and "28.27 square units" are one area.
        number = _PART_NUMBER.match(value)
        verdicts.append(asked_verdict(worked, number.group(0), names) if number else None)
    if "conflict" in verdicts:
        return "conflict"
    return "same" if all(verdict in {"same", "rounded"} for verdict in verdicts) else None


# Terms in letters added or taken away: the "m - 7n" and "-3x^2 + 6x" of an algebra answer.
# A unit after a number ("4√2 m", "8π m²"), a formula's symbols ("πr²") and a ratio's names
# ("a:b") are none.
_LETTER_TERMS = re.compile(
    r"(?<![A-Za-z\\])[a-z](?:\^\{?\d+\}?)?\s*[+\-\u2212]\s*\d*(?<![A-Za-z\\])[a-z](?![A-Za-z])"
)
_VARIABLE = re.compile(r"(?<![A-Za-z\\])[A-Za-z](?![A-Za-z])")
_UNIT_OR_WORDS = re.compile(r"\\(?:text|mathrm|operatorname)\s*\{[^{}]*\}")
_FIRST_MATH = re.compile(r"\$([^$]+)\$")
_RELATION = re.compile(r"=|\\approx|\\simeq|\u2248")


def _letters_for_a_number(worked: str, answer_body: str) -> bool:
    """The reply's Answer is an expression in letters ("m - 7n") and the card a ratio with
    none ("2:3"): no number answers it. A ratio reader took "Simplify by combining like
    terms: -(m + n) + 2(m - 3n)" for 2:3 under working that ended at m - 7n (2026-11-13)."""
    if _VARIABLE.search(_UNIT_OR_WORDS.sub(" ", answer_fence_value(answer_body))):
        return False
    lines = worked.split("\n")
    heads = [at for at, line in enumerate(lines) if answer_heading(line) is not None]
    if not heads:
        return False
    section = [answer_heading(lines[heads[-1]]) or "", *lines[heads[-1] + 1 :]]
    said = "\n".join(section).strip().split("\n\n")[0]
    main = _FIRST_MATH.search(said)  # the Answer's main value, not a later clause's
    if main is None:
        return False  # words, not maths
    value = _RELATION.split(_UNIT_OR_WORDS.sub(" ", main.group(1)))[-1]
    return _LETTER_TERMS.search(value) is not None


def _states(body: str, answer_body: str) -> bool:
    """The card states the verified value, to its rounding."""
    verdict = stated_verdict(f"**Answer**\n{answer_fence_value(body)}", answer_body)
    return verdict in {"same", "rounded"}


def rewrite_answer_fences(
    content: str, answer_body: str | None, *, withhold: bool, cap: int
) -> str:
    """The model's answer fences: gone on a hint turn; demoted with no verified value; the
    verified card in place of a lone one. In a reply of several, the verified card goes to
    the one that states the verified value (the first, when none does) and every other card
    keeps its own value, unchecked."""
    bodies = [
        content[fence.body_start : fence.body_end]
        for fence in iter_fences(content)
        if fence.closed and fence.lang in ANSWER_FENCE_LANGS
    ]
    stating = [body for body in bodies if answer_body and _states(body, answer_body)]
    checked = [stating[0] if stating else (bodies[0] if bodies else None)]

    def rewrite(body: str) -> str:
        if withhold:
            return ""
        if not answer_body:
            return demote_answer_body(body)
        if len(bodies) > 1 and body.strip("\n") != (checked[0] or "").strip("\n"):
            return _unchecked(body)
        checked[0] = "\x00"  # one verified value checks one card
        # The scan consumed the closer's newline; give it back so following text
        # never lands on the closing backticks.
        return verified_answer_fence(answer_body) + "\n"

    for lang in ANSWER_FENCE_LANGS:
        # Past the cap a model fence is still the model's: demote it, never leave it
        # standing as a card.
        content = map_closed_fences(
            content,
            lang,
            rewrite,
            max_count=cap,
            leftover=lambda body: "" if withhold else demote_answer_body(body),
        )
    return content
