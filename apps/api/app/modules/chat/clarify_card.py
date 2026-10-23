"""The ```clarify card a reply asks with: read, checked and settled before it is saved.

The model writes the card (``prompt_constants/clarify.py``); this keeps one valid card at
the end of the reply, in the shape the phone draws (docs/clarify.md). A card that breaks
the rules is not shown: a reply that only asked keeps its questions as a short line of
prose so the user still knows what was asked. A turn that must never ask (a solved
problem, an instant reply, a reminder, a picture, a multi-part reply) loses the card: the
finalize pass (``finalize_text.settle_clarify``) says which turns those are.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.services.md_fence_scan import Fence, iter_fences

logger = logging.getLogger(__name__)

CLARIFY_FENCE = "clarify"
MAX_QUESTIONS = 3
MIN_OPTIONS = 2
MAX_OPTIONS = 8
_MAX_LABEL = 60
_MAX_QUESTION = 200
_MAX_OPTION = 80
_MAX_SENTENCE = 200
_MAX_SUBMIT = 40
# Words of prose outside an invalid card above which the reply already answers.
_ANSWER_WORDS = 40
# A reply holding one of these may never ask: a solved answer, a reminder, a photo.
NEVER_WITH_CARD = frozenset({"answer", "result", "final", "reminder", "reminder_proposal", "photo"})
# What an option may start with before its words: an emoji, a flag, a joiner, a skin tone.
_LEADING_MARKS = frozenset({"So", "Sk", "Mn", "Me", "Cf"})
# A keycap emoji ("1️⃣"): a digit, # or * with the keycap mark.
_KEYCAP = re.compile("[0-9#*]\ufe0f?\u20e3")
# What only an emoji has: a pictograph past U+1F000, presentation, a joiner, a keycap.
_EMOJI_ONLY = frozenset("\ufe0f\u200d\u20e3")


def _text(value: object) -> str:
    return " ".join(str(value).split()) if isinstance(value, str | int | float) else ""


def _short(value: object, limit: int) -> str:
    """Optional card text: dropped, not refused, when it is too long to show."""
    text = _text(value)
    return text if len(text) <= limit else ""


def option_value(option: str) -> str:
    """An option as the user's message says it: "💰 Making money" is "Making money".

    Only a leading emoji goes: symbols a space ends, or that only an emoji has. A symbol
    that is part of the words stays ("°C", "№1").
    """
    keycap = _KEYCAP.match(option)
    start = keycap.end() if keycap else 0
    while start < len(option) and unicodedata.category(option[start]) in _LEADING_MARKS:
        start += 1
    lead = option[:start]
    emoji = any(ord(char) >= 0x1F000 or char in _EMOJI_ONLY for char in lead)
    if not emoji and not option[start : start + 1].isspace():
        return option
    return option[start:].strip() or option


class ClarifyQuestion(BaseModel):
    """One question: its short label, what the card shows, and 2 to 8 choices.

    ``options`` are drawn as written, emoji first; ``values`` say the same choices as the
    user's message puts them, one per option.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    label: str = Field(min_length=1, max_length=_MAX_LABEL)
    question: str = Field(min_length=1, max_length=_MAX_QUESTION)
    options: list[str] = Field(min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)
    values: list[str]

    @field_validator("options")
    @classmethod
    def _short_options(cls, options: list[str]) -> list[str]:
        if any(not option or len(option) > _MAX_OPTION for option in options):
            raise ValueError("an option is empty or too long")
        return options

    @model_validator(mode="after")
    def _value_per_option(self) -> ClarifyQuestion:
        if len(self.values) != len(self.options) or not all(self.values):
            raise ValueError("every option needs its value")
        return self


class ClarifyCard(BaseModel):
    """The questions, the button, and the sentences the sent message opens and closes with."""

    model_config = ConfigDict(extra="ignore")

    questions: list[ClarifyQuestion] = Field(min_length=1, max_length=MAX_QUESTIONS)
    request: str = Field(default="", max_length=_MAX_SENTENCE)
    closing: str = Field(default="", max_length=_MAX_SENTENCE)
    submit: str = Field(default="", max_length=_MAX_SUBMIT)

    def fence(self) -> str:
        body = json.dumps(
            self.model_dump(exclude_defaults=True), ensure_ascii=False, separators=(",", ":")
        )
        return f"```{CLARIFY_FENCE}\n{body}\n```"


def _options(raw: object) -> list[str]:
    """Trimmed, without blanks, repeats (by value, ignoring case) or choices too long to
    tap, in the model's order, and at most eight."""
    seen: set[str] = set()
    options: list[str] = []
    for option in raw if isinstance(raw, list) else []:
        text = _text(option)
        key = option_value(text).casefold()
        if text and len(text) <= _MAX_OPTION and key not in seen:
            seen.add(key)
            options.append(text)
    return options[:MAX_OPTIONS]


def _question(raw: object, index: int) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    question = _text(raw.get("question"))
    label = _text(raw.get("label")) or question.rstrip("?").strip()
    options = _options(raw.get("options"))
    return {
        "id": _text(raw.get("id")) or f"q{index + 1}",
        "label": label,
        "question": question,
        "options": options,
        "values": [option_value(option) for option in options],
    }


def read_card(body: str) -> ClarifyCard | None:
    """The card a fence body holds, normalised, or None when it breaks the rules.

    More than three questions keeps the first three, and more than eight choices the
    first eight; a question left with fewer than two choices makes the card invalid. A
    request, closing or button too long to show is dropped. A refused card is logged by
    its reason only, never its text.
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
    try:
        return ClarifyCard.model_validate(
            {
                "questions": questions,
                "request": _short(raw.get("request"), _MAX_SENTENCE),
                "closing": _short(raw.get("closing"), _MAX_SENTENCE),
                "submit": _short(raw.get("submit"), _MAX_SUBMIT),
            }
        )
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


def _holds_a_card(text: str, fence: Fence) -> bool:
    """A ```clarify fence, or our card in a ```json or bare fence: shown as JSON otherwise.

    Only the card has "request" and "submit" beside its questions, so a quiz's JSON the
    user asked for stays code.
    """
    if fence.lang == CLARIFY_FENCE:
        return True
    if fence.lang not in ("json", ""):
        return False
    try:
        raw = json.loads(text[fence.body_start : fence.body_end])
    except ValueError:
        return False
    return (
        isinstance(raw, dict)
        and isinstance(raw.get("questions"), list)
        and "request" in raw
        and "submit" in raw
    )


# Our lead-in (prompt_constants/clarify.py) made to fit the card it introduces: "one thing"
# over two questions, and a "But" with no options before it, read wrong. A reply in
# another language follows the prompt's own rule.
_LEAD_IN = re.compile(
    r"\*\*(?:but\s+)?let\s+me\s+ask\s+you\s+(?:one\s+thing|a\s+couple\s+of\s+things|"
    r"a\s+few\s+things)\.?\*\*",
    re.IGNORECASE,
)
_HOW_MANY = {1: "one thing", 2: "a couple of things"}


def _fit_lead_in(prose: str, questions: int) -> str:
    lines = prose.split("\n")
    for index in range(len(lines) - 1, -1, -1):
        if _LEAD_IN.fullmatch(lines[index].strip()):
            after_options = any("**" in line for line in lines[:index])
            opener = "But let me" if after_options else "Let me"
            lines[index] = f"**{opener} ask you {_HOW_MANY.get(questions, 'a few things')}.**"
            break
    return "\n".join(lines)


def settle_clarify_cards(text: str, *, allowed: bool, after_card: bool = False) -> str:
    """At most one valid card, last in the reply; none when the turn may not ask.

    A card that cannot be shown leaves an answer as it is; a reply that only asked keeps
    its questions as prose, so the user still knows what to answer. The turn after a
    card (``after_card``) keeps no questions at all: the user already answered.
    """
    fences = [fence for fence in iter_fences(text) if _holds_a_card(text, fence)]
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
    if allowed:
        card = next((c for body in bodies if (c := read_card(body))), None)
        if card is not None:
            prose = _fit_lead_in(prose, len(card.questions))
            return f"{prose}\n\n{card.fence()}" if prose else card.fence()
    if after_card:
        return _without_card_intro(prose)
    if len(prose.split()) > _ANSWER_WORDS:
        return prose
    asked = next((q for body in bodies if (q := _questions_only(body))), "")
    return "\n\n".join(part for part in (prose, asked) if part)


def _without_card_intro(prose: str) -> str:
    """The prose minus the lines that only led into the card: "A few more questions:", or
    the ask before it ("**But let me ask you one thing.**", "What do you mean by *best*?").

    The first line is kept, so the reply is never left empty.
    """
    lines = prose.rstrip().splitlines()
    end = len(lines)
    while end > 1 and _leads_into_card(lines[end - 1]):
        end -= 1
    return "\n".join(lines[:end]).rstrip()


def _leads_into_card(line: str) -> bool:
    text = line.strip()
    bold_only = text.startswith("**") and text.endswith("**")
    return not text or text.endswith((":", "?")) or bold_only
