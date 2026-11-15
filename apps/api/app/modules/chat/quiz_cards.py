"""A quiz card's answer is the one its own explanation reaches; the cards a reply holds.

Live (2026-10-24): "A gas has a volume of 4.0 L at 2 atm. What is the new volume if the
pressure is increased to 8 atm?", options ["1.0 L", "2.0 L", "0.5 L", "16.0 L"], answer 2
(0.5 L). Its explanation worked it out, doubted itself ("Wait, let me re-calc … Actually,
option C is 0.5L? Let's check options …") and ended "Correct answer is 1.0 L (Option A)".
The card marked the learner's right answer wrong.

Only that failure is repaired: an explanation that corrects itself ("Wait,", "let me
re-calc", "I made a mistake") and then states its answer outright ("Correct answer is
1.0 L", "The answer is (A)"). The card's answer follows that statement, and the
second-guessing is cut from what the learner reads: the working before it stays when it
reaches the same option, else the answer alone. A statement that is negated or names a
distractor ("a common wrong answer is 0.5 L", "the answer isn't C") moves nothing, nor
does a rhetorical "Hmm", and a card whose answer is not an option index is left alone.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.services.md_fence_scan import Fence, block_end, iter_fences, map_fence_blocks

QUIZ_LANG = "quiz"


# A card as one line (its question, code and options): what a chat's earlier cards are listed
# as, and what a new card is matched against. Python quizzes ask "What will this Python code
# print?" of every card, so the question alone named a different card the same.
_LINE_CHARS = 240


@dataclass(frozen=True)
class PracticeCard:
    """A ```quiz card as the learner sees it: its label, question, code, options and right
    one."""

    label: str
    question: str
    options: tuple[str, ...]
    answer: int | None
    code: str = ""

    @property
    def right(self) -> str | None:
        """The right option's words, when the card names one."""
        if self.answer is None or not 0 <= self.answer < len(self.options):
            return None
        return self.options[self.answer]

    @property
    def line(self) -> str:
        """The whole card on one line."""
        parts = [self.question]
        if self.code:
            parts.append(f"Code: {self.code}")
        if self.options:
            parts.append(f"Options: {'; '.join(self.options)}")
        return " ".join(" ".join(parts).split())[:_LINE_CHARS]


def option_letter(index: int) -> str:
    """An option's letter as the card shows it: 0 is A."""
    return chr(ord("A") + index)


def _practice_card(body: str) -> PracticeCard | None:
    try:
        card = json.loads(body)
    except (ValueError, RecursionError):
        # A model's card nested past the parser's depth is no card, never a failed turn.
        return None
    if not isinstance(card, dict) or not isinstance(question := card.get("question"), str):
        return None
    raw = card.get("options")
    options = tuple(str(o) for o in raw) if isinstance(raw, list) else ()
    answer = card.get("answer")
    label = card.get("label")
    code = card.get("code")
    return PracticeCard(
        label=label.strip() if isinstance(label, str) else "",
        question=question.strip(),
        options=options,
        answer=answer if isinstance(answer, int) and not isinstance(answer, bool) else None,
        code=code.strip() if isinstance(code, str) else "",
    )


def practice_cards(text: str | None) -> list[PracticeCard]:
    """Each closed ```quiz card in ``text`` that asks a question, in order."""
    if not text or f"```{QUIZ_LANG}" not in text:
        return []
    found = (
        _practice_card(text[fence.body_start : fence.body_end])
        for fence in iter_fences(text)
        if fence.closed and fence.lang == QUIZ_LANG
    )
    return [card for card in found if card is not None and card.question]


def block_end_of_cards(text: str) -> int:
    """Where the reply's last ```quiz card ends: what follows is its closing words."""
    ends = [
        block_end(text, fence)
        for fence in iter_fences(text)
        if fence.closed and fence.lang == QUIZ_LANG
    ]
    return max(ends, default=len(text))


def last_reply_cards(messages: Sequence[Any] | None) -> list[PracticeCard]:
    """The cards with options the last assistant reply of an oldest-first window ends on:
    the practice the next message may answer."""
    for message in reversed(messages or []):
        if getattr(message, "role", None) != "assistant":
            continue
        content = getattr(message, "content", None)
        return [card for card in practice_cards(content) if card.options]
    return []


# Where the model corrects itself: everything from here is thinking aloud. Not "actually"
# ("it actually doubles"), a bare "wait" ("wait 2 s"), "Hmm" or "Hold on", which teach.
_DOUBT = re.compile(
    r"\bwait(?=\s*[,.!\u2014\u2013-])|\blet me (?:re-?(?:calc\w*|check|do|think|compute)|"
    r"double-check)\b|\blet's (?:re-?|double-)check\b|\bi made an? (?:mistake|error)\b|"
    r"\bcorrection:",
    re.IGNORECASE,
)
# "Correct answer is 1.0 L", "The answer is (A)", "Answer: 1.0 L" — not "isn't" / "is not".
_STATED = re.compile(
    r"\b(?:correct answer|the answer|answer)\s*(?:is(?!n['\u2019]t)\b(?!\s+not\b)|:|=)", re.I
)
# "A common wrong answer is", "a tempting answer is": a distractor, not the conclusion.
_DISTRACTOR = re.compile(r"\b(?:wrong|incorrect|common|tempting|mistaken|bad)\s+$", re.I)
_LETTER = re.compile(r"\b(?:option|answer|choice)\s*\(?([A-H])\)?(?![\w'])|\(([A-H])\)", re.I)
_TEXT_NOISE = re.compile(r"[\s$\\{}]+|\\text|\\mathrm")


def _plain(text: str) -> str:
    return _TEXT_NOISE.sub("", text).casefold()


def _named(text: str, options: list[str]) -> list[int]:
    """The options ``text`` names, by their own words or by letter, in order of mention."""
    flat = _plain(text)
    found: list[tuple[int, int]] = []
    for index, option in enumerate(options):
        word = _plain(option)
        at = flat.find(word) if word else -1
        if at >= 0:
            found.append((at, index))
    named = [index for _at, index in sorted(found)]
    for match in _LETTER.finditer(text):
        letter = (match.group(1) or match.group(2)).upper()
        index = ord(letter) - ord("A")
        if index < len(options):
            named.append(index)
    return named


def _concluded(explanation: str, options: list[str]) -> int | None:
    """The one option a self-correcting explanation states last, or None."""
    if _DOUBT.search(explanation) is None:
        return None
    last = _DOUBT.split(explanation)[-1]
    stated = [m for m in _STATED.finditer(last) if not _DISTRACTOR.search(last[: m.start()])]
    if not stated:
        return None
    named = set(_named(last[stated[-1].start() :], options))
    return named.pop() if len(named) == 1 else None


def _settled(explanation: str, options: list[str], answer: int, moved: bool) -> str:
    """The explanation without its second-guessing: the working before the first doubt
    when it reaches ``answer``, else the answer alone when the answer ``moved`` (an
    explanation that never settles stays, rather than asserting the card's own pick)."""
    if not _DOUBT.search(explanation):
        return explanation
    before = _DOUBT.split(explanation, maxsplit=1)[0].strip().rstrip(",;:")
    if before and answer in _named(before, options):
        return before
    return f"The answer is {options[answer]}." if moved else explanation


def _repaired(card: dict[str, Any]) -> dict[str, Any] | None:
    options, explanation, given = card.get("options"), card.get("explanation"), card.get("answer")
    if not isinstance(options, list) or not all(isinstance(o, str) for o in options):
        return None
    if not isinstance(explanation, str) or not explanation.strip():
        return None
    if not isinstance(given, int) or isinstance(given, bool) or not 0 <= given < len(options):
        return None
    concluded = _concluded(explanation, options)
    answer = given if concluded is None else concluded
    settled = _settled(explanation, options, answer, answer != given)
    if answer == given and settled == explanation:
        return None
    return {**card, "answer": answer, "explanation": settled}


def repair_quiz_fences(text: str) -> str:
    """Each quiz card with its answer set to the one its explanation reaches."""
    if f"```{QUIZ_LANG}" not in text:
        return text

    def replace(fence: Fence, body: str) -> str:
        original = text[fence.start : block_end(text, fence)]
        try:
            card = json.loads(body)
        except ValueError:
            return original
        fixed = _repaired(card) if isinstance(card, dict) else None
        if fixed is None:
            return original
        closer = text[fence.body_end : block_end(text, fence)]
        opener = text[fence.start : fence.body_start]
        return f"{opener}{fence.opener.prefix}{json.dumps(fixed, ensure_ascii=False)}\n{closer}"

    return map_fence_blocks(text, replace, lang=QUIZ_LANG)
