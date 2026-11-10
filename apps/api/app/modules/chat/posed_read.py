"""The problem "do it" means, when the assistant posed it: a fast model reads the chat.

Live (2026-11-10) "Give me physics question for grade 7th" got "A car travels 120 meters in
20 seconds. What is its speed?", and "Do it", "How" and "Step by step" after it reached no
solver: the subjects' follow-up readers look for the problem in the user's own last line,
and here the assistant had stated it. Typed by the user, the same question gets the worked
layout and a verified card. So on a short line after a reply, with no subject of its own,
one small structured read (``referent_read.ask_read``) names the message, the assistant's
or the user's, that states the problem the line asks to solve or to change ("What if h was
10 m?", a tapped follow-up question), the problem as written there, and for a change the
problem restated with it. The restatement is held to the words it came from: its numbers
are the problem's and the line's, and the line's new value is in it. The quiz guard holds:
a line that answers a question ("the hypotenuse") asks no solve. With no read, or none
named, the turn is read as before.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.readings import keep_for_turn, kept_for_turn
from app.modules.chat.referent_read import ask_read, chat_before
from app.services.text_normalize import collapse_ws

logger = logging.getLogger(__name__)

# A line that only refers to a problem: "Do it", "Step by step", "What if it took 10 s?".
_MAX_WORDS = 12
_MESSAGE_CHARS = 500
# Markdown a stated problem may carry: "A car travels **120 meters**".
_EMPHASIS = re.compile(r"[*_`]+")
# A value, with its sign when the minus is its own ("y = -2x"); never a subscript ("$T_1$").
# Sentences after the problem that exclaim: "Give it a try!", "Good luck! \U0001f680".
_CHEER = re.compile(r"(?<=[.?])(?:\s+[^.?!]*!+[^\w.?]*)+$")
_NUMBER = re.compile(r"(?:(?<![\w)\]])-)?(?<![_{\d.])\d+(?:\.\d+)?")
_WORD = re.compile(r"[^\W\d_]+")
# The words of a restatement its problem and line do not hold: "now", "instead", an article.
_NEW_WORDS = 0.2

_SYSTEM = (
    "The conversation's messages are numbered, the assistant's too. The user's last message "
    "is short. Say what it asks, as kind:\n"
    '- "solve": to solve a problem stated earlier, by the user or posed by the assistant as '
    "a practice question, a quiz or an example, exactly as it stands: do it, solve it, "
    "what's the answer, step by step, show the working, and how, even the one word "
    '"How" alone, which asks how that problem is solved;\n'
    '- "change": the same problem with one of its values changed ("what if it took 10 s?", '
    '"what if the mass was 500 g?"), or asking for another quantity of the same setup '
    '("how far does it go?");\n'
    '- "answer": the user answers a question themselves (a quiz answer, a value they were '
    "asked for, yes or no);\n"
    '- "other": anything else: why a step works, how one thing affects another, a new '
    "problem, accepting an offer to do something that is no problem to solve.\n"
    "For solve and change, message is the number of the message that states the problem, "
    "and problem is the problem as that message states it, copied word for word, without "
    "greetings, praise or offers. For change, changed is that problem asked again with the "
    "change: the new value in place of the one it replaces, or the other quantity asked, "
    "every other word kept. Otherwise all null. Reply with JSON only, for example "
    '{"kind": "change", "message": 2, "problem": "A ball falls 20 m. How long does it take?", '
    '"changed": "A ball falls 45 m. How long does it take?"}.'
)


@dataclass(frozen=True)
class Posed:
    """The problem a short line refers to, as its message states it. ``changed`` when the
    line changes one of its values, ``restated`` the problem with it, when the read's
    restatement holds (``held_restatement``)."""

    problem: str
    reply: str
    changed: bool = False
    restated: str | None = None


class PosedPick(BaseModel):
    kind: Literal["solve", "change", "answer", "other"]
    message: int | None = None
    problem: str | None = Field(default=None, max_length=600)
    changed: str | None = Field(default=None, max_length=700)


def _numbered(exchanges: Sequence[tuple[str, str]]) -> str:
    return "\n".join(
        f"[{index}] {'User' if role == 'user' else 'Assistant'}: "
        f"{collapse_ws(text)[:_MESSAGE_CHARS]}"
        for index, (role, text) in enumerate(exchanges, start=1)
    )


def _plain(text: str) -> str:
    return collapse_ws(_EMPHASIS.sub("", text))


def _stated(role: str, message: str, quoted: str | None) -> str | None:
    """The problem as the message states it: the model's copy when it is word for word the
    message's own; else a user's whole message, as typed, and no problem from a reply."""
    whole = _plain(message)
    copy = _plain(quoted or "")
    if copy and copy.casefold() in whole.casefold():
        # "Give it a try!" after the question is the reply's cheer, not the problem's.
        return _CHEER.sub("", copy) or copy
    return whole if role == "user" else None


def _numbers(text: str) -> Counter[Decimal]:
    out: Counter[Decimal] = Counter()
    for found in _NUMBER.findall(text):
        try:
            out[Decimal(found).normalize()] += 1
        except InvalidOperation:
            continue
    return out


def held_restatement(problem: str, line: str, restated: str | None) -> str | None:
    """The read's restatement of ``problem`` with the change ``line`` asks, when it holds to
    them. Every number in it is the problem's or the line's (a value it worked out itself is
    no restatement). A line with a value replaces one of the problem's with it ("what if
    the mass was 20 kg?"; "... if M was 50 g/mol" tacked on changes nothing a solver reads);
    a line without one asks another quantity, every value kept. And almost every word is
    theirs. "What if it was 3 times higher?" is left to the subjects' readers, which scale a
    given; "what if gravity was weaker?" to the model."""
    if not restated:
        return None
    text = _plain(restated)
    if text.casefold() == _plain(problem).casefold():
        return None
    given, asked, have = _numbers(problem), _numbers(line), _numbers(text)
    if have - (given + asked) or asked - have:
        return None
    if (not given - have) if asked else have != given:
        return None
    known = {word.casefold() for word in _WORD.findall(f"{problem} {line}")}
    words = [word.casefold() for word in _WORD.findall(text)]
    new = sum(word not in known for word in words)
    return text if words and new <= _NEW_WORDS * len(words) else None


async def pick_posed(settings: Settings, line: str, conversation: str) -> PosedPick | None:
    """The model's read of the problem a short line refers to, or None when there is no read."""
    return await ask_read(settings, _SYSTEM, line, conversation, PosedPick, max_tokens=400)


def may_refer_to_a_problem(line: str, recent: Sequence[Any]) -> bool:
    """A cheap look before any read: a short line right after a reply that states numbers or
    asks something."""
    words = collapse_ws(line).split()
    if not words or len(words) > _MAX_WORDS:
        return False
    exchanges = chat_before(recent, line)
    if not exchanges or exchanges[-1][0] != "assistant":
        return False
    reply = exchanges[-1][1]
    return "?" in reply or any(char.isdigit() for char in reply)


_KEPT = "posed"


async def posed_for_turn(settings: Settings, line: str, recent: Sequence[Any]) -> Posed | None:
    """``read_posed`` once a turn, kept as the other reads are (``core.readings``)."""
    # Keyed by the chat too: a run of turns outside a request (the sweep) shares one memo.
    key = (line, tuple(chat_before(recent, line)))
    kept = kept_for_turn(_KEPT)
    if isinstance(kept, tuple) and kept[0] == key:
        posed: Posed | None = kept[1]
        return posed
    posed = await read_posed(settings, line, recent)
    keep_for_turn(_KEPT, (key, posed))
    return posed


async def read_posed(settings: Settings, line: str, recent: Sequence[Any]) -> Posed | None:
    """The problem a short line asks to solve or change, as its message states it; None with
    no read, or when the line answers a question or asks no solve."""
    if not settings.referent_read_enabled or not may_refer_to_a_problem(line, recent):
        return None
    exchanges = chat_before(recent, line)
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
    changed = read.kind == "change"
    return Posed(
        problem=problem,
        reply=exchanges[-1][1],
        changed=changed,
        restated=held_restatement(problem, line, read.changed) if changed else None,
    )
