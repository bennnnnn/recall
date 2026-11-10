"""The problem "do it" means, when the assistant posed it: a fast model reads the chat.

Live (2026-11-10) "Give me physics question for grade 7th" got "A car travels 120 meters in
20 seconds. What is its speed?", and "Do it", "How" and "Step by step" after it reached no
solver: the subjects' follow-up readers look for the problem in the user's own last line,
and here the assistant had stated it. Typed by the user, the same question gets the worked
layout and a verified card. So on a short line with no subject of its own, after a reply
whose exchange holds a problem a subject reads (the reply's question, or the user's line
before it), one small structured read (``referent_read.ask_read``) names the message, the
assistant's or the user's, that states the problem the line asks to solve or to change
("What if h was 10 m?", a tapped follow-up question), and the problem as written there. A
change is named, never written: the given that changes and the line's new value, which the
problem's subject puts in its place (``SubjectFollowups.changed_problem``). The quiz guard
holds: a line that answers a question ("the hypotenuse") asks no solve. The read starts as
the turn loads and is awaited only when no reader claimed the line; with no read, or none
named, the turn is read as before.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.readings import keep_for_turn, kept_for_turn, read_off_loop
from app.modules.chat.referent_read import ask_read, chat_before
from app.services.text_normalize import collapse_ws

logger = logging.getLogger(__name__)

# A line that only refers to a problem: "Do it", "Step by step", "What if it took 10 s?".
_MAX_WORDS = 12
_MESSAGE_CHARS = 500
# A reply short enough to be a posed problem; a longer one is read for its exchange's line.
_REPLY_CHARS = 600
# Markdown a stated problem may carry: "A car travels **120 meters**"; a subscript stays.
_EMPHASIS = re.compile(r"\*+|`+|(?<!\w)_+|_+(?!\w)")
# Sentences after the problem that exclaim: "Give it a try!", "Good luck! \U0001f680".
_CHEER = re.compile(r"(?<=[.?])(?:\s+[^.?!]*!+[^\w.?]*)+$")
# LaTeX a line's value may come in: "$T_C = 200\\,\\mathrm{K}$" is "T_C = 200 K".
_LATEX_WORD = re.compile(r"\\(?:mathrm|text|operatorname)\s*\{([^{}]*)\}")
_LATEX_SPACE = re.compile(r"\\[,;: !]|\$")


_SYSTEM = (
    "The conversation's messages are numbered, the assistant's too. The user's last message "
    "is short. Say what it asks, as kind:\n"
    '- "solve": to solve a problem stated earlier, by the user or posed by the assistant as '
    "a practice question, a quiz or an example, exactly as it stands and asking nothing "
    "else of it: do it, solve it, what's the answer, step by step, show the working, and "
    'how, even the one word "How" alone, which asks how that problem is solved;\n'
    '- "change": the same problem with one of its values changed ("what if it took 10 s?", '
    '"what if the mass was 500 g?");\n'
    '- "answer": the user answers a question themselves (a quiz answer, a value they were '
    "asked for, yes or no);\n"
    '- "other": anything else: a question that asks something else of the problem (another '
    'quantity, "how do I find the x-intercept?" after a y-intercept, "what is the quotient?" '
    "after a remainder), why a step works, how one thing affects another, a new problem, "
    "accepting an offer to do something that is no problem to solve.\n"
    "For solve and change, message is the number of the message that states the problem, "
    "and problem is the problem as that message states it, copied word for word, without "
    "greetings, praise or offers. For change, given is the value that changes as the "
    "problem writes it (20 seconds, 16.0 g of oxygen), or in an equation or expression the "
    "part it replaces, copied exactly; and new is the new value as the user's line gives "
    "it, in plain text with its unit (10 s, 32.0 g, 2x). Otherwise all null. Reply with "
    'JSON only, for example {"kind": "change", "message": 2, "problem": "A ball falls 20 m. '
    'How long does it take?", "given": "20 m", "new": "45 m"}.'
)


@dataclass(frozen=True)
class Posed:
    """The problem a short line refers to, as its message states it. A change names the
    given that changes (``given``) and the line's new value (``new``); the problem's
    subject puts it in place, or the change is no solve."""

    problem: str
    reply: str
    changed: bool = False
    given: str | None = None
    new: str | None = None


class PosedPick(BaseModel):
    kind: Literal["solve", "change", "answer", "other"]
    message: int | None = None
    problem: str | None = Field(default=None, max_length=600)
    given: str | None = Field(default=None, max_length=120)
    new: str | None = Field(default=None, max_length=60)


def _numbered(exchanges: Sequence[tuple[str, str]]) -> str:
    return "\n".join(
        f"[{index}] {'User' if role == 'user' else 'Assistant'}: "
        f"{collapse_ws(text)[:_MESSAGE_CHARS]}"
        for index, (role, text) in enumerate(exchanges, start=1)
    )


def _plain(text: str) -> str:
    return collapse_ws(_EMPHASIS.sub("", text))


def _unlatexed(text: str) -> str:
    return collapse_ws(_LATEX_SPACE.sub(" ", _LATEX_WORD.sub(r"\1", text))).casefold()


def _stated(role: str, message: str, quoted: str | None) -> str | None:
    """The problem as the message states it: the model's copy when it is word for word the
    message's own; else a user's whole message, as typed, and no problem from a reply."""
    whole = _plain(message)
    copy = _plain(quoted or "")
    if copy and copy.casefold() in whole.casefold():
        # "Give it a try!" after the question is the reply's cheer, not the problem's.
        return _CHEER.sub("", copy) or copy
    return whole if role == "user" else None


def _line_value(line: str, new: str | None) -> str | None:
    """The new value as the line gives it: the read's copy only when the line holds it."""
    value = _unlatexed(new or "")
    return collapse_ws(new or "") if value and value in _unlatexed(line) else None


def holds_a_problem(asked: str | None, reply: str) -> bool:
    """Whether the exchange before the line holds a problem a subject reads: the reply's own
    (a practice question it posed) or the user's line it answered. Read in the pool."""
    from app.modules.chat.turn_prep.reading import subject_of

    if asked and subject_of(asked) is not None:
        return True
    plain = _plain(reply)
    return len(plain) <= _REPLY_CHARS and subject_of(plain) is not None


async def pick_posed(settings: Settings, line: str, conversation: str) -> PosedPick | None:
    """The model's read of the problem a short line refers to, or None when there is no read."""
    return await ask_read(settings, _SYSTEM, line, conversation, PosedPick, max_tokens=160)


def may_refer_to_a_problem(line: str, recent: Sequence[Any]) -> bool:
    """A cheap look on the loop: a short line right after a reply."""
    words = collapse_ws(line).split()
    if not words or len(words) > _MAX_WORDS:
        return False
    exchanges = chat_before(recent, line)
    return bool(exchanges) and exchanges[-1][0] == "assistant"


_KEPT = "posed"


def _key(line: str, recent: Sequence[Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
    # Keyed by the chat too: a run of turns outside a request (the sweep) shares one memo.
    return line, tuple(chat_before(recent, line))


# The read started as the turn loaded. Beside the turn's readings, not in them: the
# readings are copied to the SymPy pool's workers, and a task does not pickle.
_STARTED: ContextVar[tuple[Any, asyncio.Task[Posed | None]] | None] = ContextVar(
    "posed_read_started", default=None
)


def start_posed_read(settings: Settings, line: str, recent: Sequence[Any]) -> None:
    """Start the read as the turn loads, beside its other reads: the turn awaits it only
    when no subject reader claims the line (``posed_for_turn``), so it adds no wait to a
    turn that never asks."""
    if not settings.referent_read_enabled or not may_refer_to_a_problem(line, recent):
        return
    task = asyncio.create_task(read_posed(settings, line, recent), name="posed_read")
    _STARTED.set((_key(line, recent), task))


async def posed_for_turn(settings: Settings, line: str, recent: Sequence[Any]) -> Posed | None:
    """The turn's read: the one started as it loaded, else read now (``core.readings``)."""
    key = _key(line, recent)
    started = _STARTED.get()
    if started is not None and started[0] == key:
        return await started[1]
    kept = kept_for_turn(_KEPT)
    if isinstance(kept, tuple) and kept[0] == key:
        posed: Posed | None = kept[1]
        return posed
    posed = await read_posed(settings, line, recent)
    keep_for_turn(_KEPT, (key, posed))
    return posed


async def read_posed(settings: Settings, line: str, recent: Sequence[Any]) -> Posed | None:
    """The problem a short line asks to solve or change, as its message states it; None with
    no read, after an exchange that holds no problem, or when the line answers a question
    or asks no solve."""
    if not settings.referent_read_enabled or not may_refer_to_a_problem(line, recent):
        return None
    exchanges = chat_before(recent, line)
    asked = exchanges[-2][1] if len(exchanges) > 1 and exchanges[-2][0] == "user" else None
    held = await read_off_loop(
        holds_a_problem,
        asked,
        exchanges[-1][1],
        timeout=settings.subject_read_timeout_seconds,
    )
    if not held:
        return None
    started = time.perf_counter()
    read = await pick_posed(settings, collapse_ws(line), _numbered(exchanges))
    logger.info("posed read took %.0f ms", (time.perf_counter() - started) * 1000)
    if read is None or read.kind not in ("solve", "change") or read.message is None:
        return None
    if not 1 <= read.message <= len(exchanges):
        return None
    problem = _stated(*exchanges[read.message - 1], read.problem)
    if problem is None:
        return None
    if read.kind == "solve":
        return Posed(problem=problem, reply=exchanges[-1][1])
    return Posed(
        problem=problem,
        reply=exchanges[-1][1],
        changed=True,
        given=collapse_ws(read.given or "") or None,
        new=_line_value(line, read.new),
    )
