"""The ```clarify card a reply asks with: read, checked and settled before it is saved.

The model writes the card (``prompt_constants/clarify.py``); this keeps one valid card at
the end of the reply, in the shape the phone draws (docs/clarify.md). A card that breaks
the rules is not shown: a "first" reply keeps its questions as a short line of prose so
the user still knows what was asked. A turn that must never ask (a solved problem, an
instant reply, a reminder, a picture, a multi-part reply) loses the card: the finalize
pass (``finalize_text.settle_clarify``) says which turns those are.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.services.md_fence_scan import iter_fences

logger = logging.getLogger(__name__)

CLARIFY_FENCE = "clarify"
MAX_QUESTIONS = 3
MIN_OPTIONS = 2
MAX_OPTIONS = 4
_MAX_LABEL = 60
_MAX_QUESTION = 200
_MAX_OPTION = 80
# Words of prose outside the card above which a card with no "when" is under an answer.
_ANSWER_WORDS = 40
# A reply holding one of these may never ask: a solved answer, a reminder, a photo.
NEVER_WITH_CARD = frozenset({"answer", "result", "final", "reminder", "reminder_proposal", "photo"})


def _text(value: object) -> str:
    return " ".join(str(value).split()) if isinstance(value, str | int | float) else ""


class ClarifyQuestion(BaseModel):
    """One question: its short label, what the card shows, and 2 to 4 choices."""

    model_config = ConfigDict(extra="ignore")

    id: str
    label: str = Field(min_length=1, max_length=_MAX_LABEL)
    question: str = Field(min_length=1, max_length=_MAX_QUESTION)
    options: list[str] = Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)
    multi: bool = False

    @field_validator("options")
    @classmethod
    def _short_options(cls, options: list[str]) -> list[str]:
        if any(not option or len(option) > _MAX_OPTION for option in options):
            raise ValueError("an option is empty or too long")
        return options


class ClarifyCard(BaseModel):
    model_config = ConfigDict(extra="ignore")

    when: Literal["first", "after"]
    questions: list[ClarifyQuestion] = Field(min_length=1, max_length=MAX_QUESTIONS)

    def fence(self) -> str:
        body = json.dumps(self.model_dump(), ensure_ascii=False, separators=(",", ":"))
        return f"```{CLARIFY_FENCE}\n{body}\n```"


def _options(raw: object) -> list[str]:
    """Trimmed, without blanks, repeats (ignoring case) or choices too long to tap, in the
    model's order, and at most four: the card's Other... covers a fifth."""
    seen: set[str] = set()
    options: list[str] = []
    for option in raw if isinstance(raw, list) else []:
        text = _text(option)
        if text and len(text) <= _MAX_OPTION and text.casefold() not in seen:
            seen.add(text.casefold())
            options.append(text)
    return options[:MAX_OPTIONS]


def _question(raw: object, index: int) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    question = _text(raw.get("question"))
    label = _text(raw.get("label")) or question.rstrip("?").strip()
    return {
        "id": _text(raw.get("id")) or f"q{index + 1}",
        "label": label,
        "question": question,
        "options": _options(raw.get("options")),
        "multi": raw.get("multi") is True,
    }


def read_card(body: str, *, prose_words: int = 0) -> ClarifyCard | None:
    """The card a fence body holds, normalised, or None when it breaks the rules.

    More than three questions keeps the first three, and more than four choices the first
    four; a question left with fewer than two choices makes the card invalid. With no
    "when", a reply that already answers (``prose_words`` past ``_ANSWER_WORDS``) holds an
    "after" card. A refused card is logged by its reason only, never its text.
    """
    try:
        raw = json.loads(body)
    except ValueError:
        logger.info("clarify card dropped: not JSON")
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("questions"), list):
        logger.info("clarify card dropped: no questions list")
        return None
    questions = [_question(item, i) for i, item in enumerate(raw["questions"][:MAX_QUESTIONS])]
    if any(question is None for question in questions):
        logger.info("clarify card dropped: a question is not an object")
        return None
    when = raw.get("when")
    if when not in ("first", "after"):
        when = "after" if prose_words > _ANSWER_WORDS else "first"
    try:
        return ClarifyCard.model_validate({"when": when, "questions": questions})
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        logger.info("clarify card dropped: invalid %s", ", ".join(fields))
        return None


def _questions_only(body: str) -> str:
    """What a card asked, as prose lines with its choices, when its JSON can be read."""
    try:
        raw = json.loads(body)
    except ValueError:
        return ""
    items = raw.get("questions") if isinstance(raw, dict) else None
    lines: list[str] = []
    for item in (items if isinstance(items, list) else [])[:MAX_QUESTIONS]:
        question = _text(item.get("question")) if isinstance(item, dict) else ""
        if not question:
            continue
        options = _options(item.get("options"))
        lines.append(f"- {question} ({' / '.join(options)})" if options else f"- {question}")
    return "\n".join(lines)


def settle_clarify_cards(text: str, *, allowed: bool, after_card: bool = False) -> str:
    """At most one valid card, last in the reply; none when the turn may not ask.

    A card that cannot be shown leaves an answer as it is; a reply that only asked keeps
    its questions as prose, so the user still knows what to answer. The turn after a
    card (``after_card``) keeps no questions at all: the user already answered.
    """
    fences = [fence for fence in iter_fences(text) if fence.lang == CLARIFY_FENCE]
    if not fences:
        return text
    pieces: list[str] = []
    cursor = 0
    bodies: list[str] = []
    for fence in fences:
        pieces.append(text[cursor : fence.start])
        bodies.append(text[fence.body_start : fence.body_end])
        cursor = fence.end
    pieces.append(text[cursor:])
    prose = "".join(pieces).strip()
    words = len(prose.split())
    if allowed:
        card = next((c for body in bodies if (c := read_card(body, prose_words=words))), None)
        if card is not None:
            return f"{prose}\n\n{card.fence()}" if prose else card.fence()
    if after_card:
        return _without_card_intro(prose)
    if words > _ANSWER_WORDS:
        return prose
    asked = next((q for body in bodies if (q := _questions_only(body))), "")
    return "\n\n".join(part for part in (prose, asked) if part)


def _without_card_intro(prose: str) -> str:
    """The prose minus a last line that only introduced the card ("A few more questions:").

    Kept when it is all there is, so the reply is never left empty.
    """
    lines = prose.rstrip().splitlines()
    if len(lines) > 1 and lines[-1].rstrip().endswith(":"):
        return "\n".join(lines[:-1]).rstrip()
    return prose
