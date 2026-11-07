"""Which of a reply's answer cards the server's one verified value may check.

A verified card read from words that the reply's own result contradicts gets no check. The
model is shown the server's result before it writes. When it still works a question in words
to another value, the two read the question differently, and the server's reading of words is
the one in doubt: "a jacket costs 2400 shillings, 15% off, then 16% VAT" was read as a
proportion and carried a checked 0.1 under working that ended at 2366.40 (2026-11-06). The
reply then stands as the model wrote it, its own final value in a card with no check, and the
pictures of the server's reading go with it. A question in parts already worked this way in
physics (``physics.part_answers.parts_conflict``). An equation or expression the user typed is
read without doubt, so a reply that solves it to another value still gets the verified card
and its correction line.

One verified value checks one card. A reply in parts with a card per part ("c = 15 cm",
"A = 54 cm²", "P = 36 cm") had every card rewritten to the one verified value, 36 three times:
only the card that states that value gets it, and each other part keeps its own, unchecked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.answer_check import stated_verdict
from app.services.answer_fence import (
    ANSWER_FENCE_LANGS,
    UNCHECKED_ANSWER_MARKER,
    answer_fence_value,
    demote_answer_body,
    demote_answer_fences,
    land_answer_card,
    normalize_owned_fences,
    verified_answer_fence,
)
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
    if stated_verdict(demote_answer_fences(reply), answer_body) != "conflict":
        return None
    text = normalize_owned_fences(reply, ANSWER_FENCE_LANGS)
    for lang in ANSWER_FENCE_LANGS:
        text = map_closed_fences(text, lang, _unchecked)
    for lang in _PICTURE_LANGS:
        text = strip_closed_fences(text, lang)
    return land_answer_card(text.strip(), None)


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
