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
change is named, never written: each given that changes and the line's new value for it,
which the problem's subject puts in its place (``SubjectFollowups.changed_problem``). The quiz guard
holds: a line that answers a question ("the hypotenuse") asks no solve. The read runs only
where it decides the turn: no reader claimed the line, it is no small talk, and no other
read found its problem (``turn_prep.augment``); Stop cancels it with the turn. With no read,
or none named, the turn is read as before.

A line a subject claims gets the read too when, read in the pool, it holds no problem of its
own and states a value with a unit of a kind the user's problem before it gives: "Repeat the
calculation but this time take the charges as 3.0 pC and 2.0 μC", after a verified Coulomb's
law answer, was physics with no problem of its own, and its reply worked both charges out
with no check (live, 2026-11-16). Such a line may run to a few sentences. "Why is 2.16e9 N
so large?" states no value of the problem's kinds and is never read; a pool that gives up
reads nothing, and the turn goes on as typed.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.readings import keep_for_turn, kept_for_turn, read_aside
from app.modules.chat.referent_read import ask_read, chat_before
from app.services.problem_followup import stated_numbers
from app.services.solving import SubjectName
from app.services.text_normalize import collapse_ws

logger = logging.getLogger(__name__)

# A line that only refers to a problem: "Do it", "Step by step", "What if it took 10 s?".
_MAX_WORDS = 12
# A line a subject claims that restates values for a problem stated before it: a textbook's
# "repeat the calculation" question, which says why before what changes.
_MAX_RESTATED_WORDS = 80
_STATES_A_VALUE = re.compile(r"\d")

# Most values one line changes at once.
_MAX_CHANGES = 4
# The longest read fits: a 600-character problem (about 200 tokens, at three characters a
# token for numbers and units), four changes of 120 and 60 characters (about 240) and the
# JSON around them. A read cut short is no JSON, and no read.
_MAX_TOKENS = 512
_MESSAGE_CHARS = 500
# A reply short enough to be a posed problem; a longer one is read for its exchange's line.
_REPLY_CHARS = 600
# Markdown a stated problem may carry: "A car travels **120 meters**"; a subscript stays.
_EMPHASIS = re.compile(r"\*+|`+|(?<!\w)_+|_+(?!\w)")
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
    '- "change": the same problem with some of its values changed ("what if it took 10 s?", '
    '"what if the mass was 500 g?", "repeat it with the charges as 3 nC and 5 nC");\n'
    '- "answer": the user answers a question themselves (a quiz answer, a value they were '
    "asked for, yes or no);\n"
    '- "other": anything else: a question that asks something else of the problem (another '
    'quantity, "how do I find the x-intercept?" after a y-intercept, "what is the quotient?" '
    "after a remainder), why a step works, how one thing affects another, a new problem, "
    "accepting an offer to do something that is no problem to solve.\n"
    "For solve and change, message is the number of the message that states the problem, "
    "and problem is the problem as that message states it, copied word for word, without "
    "greetings, praise or offers. For change, changes lists each value that changes, one "
    "entry per value, never two values in one entry: given as the problem writes it (20 "
    "seconds, 16.0 g of oxygen), or in an equation or expression the part it replaces, "
    "copied exactly; and new as the user's line gives it, the value and its unit alone (10 "
    "s, 32.0 g, 2x), without a note around it. Otherwise null and no changes. Reply "
    'with JSON only, for example {"kind": "change", "message": 2, "problem": "A ball falls '
    '20 m. How long does it take?", "changes": [{"given": "20 m", "new": "45 m"}]}.'
)


@dataclass(frozen=True)
class Posed:
    """The problem a short line refers to, as its message states it. A change names the
    given that changes (``given``) and the line's new value (``new``); the problem's
    subject puts it in place, or the change is no solve."""

    problem: str
    reply: str
    changed: bool = False
    # Each change: the given as the problem writes it, and the line's new value (None when
    # the line does not hold the value the read gave).
    changes: tuple[tuple[str | None, str | None], ...] = ()


class PosedChange(BaseModel):
    given: str | None = Field(default=None, max_length=120)
    new: str | None = Field(default=None, max_length=60)


class PosedPick(BaseModel):
    kind: Literal["solve", "change", "answer", "other"]
    message: int | None = None
    problem: str | None = Field(default=None, max_length=600)
    changes: list[PosedChange] = Field(default_factory=list, max_length=_MAX_CHANGES)


def _numbered(exchanges: Sequence[tuple[str, str]]) -> str:
    return "\n".join(
        f"[{index}] {'User' if role == 'user' else 'Assistant'}: "
        f"{collapse_ws(text)[:_MESSAGE_CHARS]}"
        for index, (role, text) in enumerate(exchanges, start=1)
    )


def _plain(text: str) -> str:
    return collapse_ws(_EMPHASIS.sub("", text))


def _unlatexed(text: str) -> str:
    # The micro sign and the Greek mu are one prefix: a read may copy "2.0 μC" as "2.0 µC".
    plain = _LATEX_SPACE.sub(" ", _LATEX_WORD.sub(r"\1", text)).replace("\u00b5", "\u03bc")
    return collapse_ws(plain).casefold()


def _stated(role: str, message: str, quoted: str | None) -> str | None:
    """The problem as the message states it: the model's copy when it is word for word the
    message's own; else a user's whole message, as typed, and no problem from a reply."""
    whole = _plain(message)
    copy = _plain(quoted or "")
    if copy and copy.casefold() in whole.casefold():
        # "Give it a try!" after the question is the reply's cheer, not the problem's.
        return without_cheer(copy)
    return whole if role == "user" else None


def without_cheer(text: str) -> str:
    """The text without the sentences after its last "." or "?" when they exclaim: "Give
    it a try!", "Good luck! \U0001f680". One pass from the end, never a backtracking match."""
    cut = max(text.rfind("."), text.rfind("?"))
    tail = text[cut + 1 :]
    if cut < 0 or not tail[:1].isspace():
        return text
    last_word = max((index for index, char in enumerate(tail) if char.isalnum()), default=-1)
    return text[: cut + 1] if last_word >= 0 and "!" in tail[last_word:] else text


def states_new_values(line: str, problem: str) -> bool:
    """``line`` states a value ``problem`` does not: a quantity read with its unit by a
    subject ("20 minutes" after "20 seconds"), or a bare number the problem lacks, never an
    item's number ("Solve 1", "question 9"). Run in the pool (``read_posed``)."""
    from app.services.subjects.registry import SUBJECTS

    if any(adapter.followups.states_new(problem, line) for adapter in SUBJECTS):
        return True
    # As a multiset: "3x + 3 = 7" after "2x + 3 = 7" writes a second 3, a new number.
    return bool(stated_numbers(line) - stated_numbers(problem))


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


def restates_a_problem(claimed: SubjectName, asked: str | None, line: str) -> bool:
    """Whether a line ``claimed`` by a subject may change the problem the user stated before
    it: that problem is the subject's, values and all (never a request to draw: "Repeat
    question 2 for two negative charges" after "Draw the field of a charge"), the line holds
    no problem of its own, and it states a value with a unit of a kind the problem gives.
    Read in the pool."""
    from app.modules.chat.turn_prep.reading import subject_of
    from app.services.subjects.registry import subject_adapter

    if not asked or subject_of(asked) != claimed:
        return False
    adapter = subject_adapter(claimed)
    return (
        adapter.reads(asked) and not adapter.reads(line) and adapter.followups.restates(asked, line)
    )


async def pick_posed(settings: Settings, line: str, conversation: str) -> PosedPick | None:
    """The model's read of the problem a short line refers to, or None when there is no read."""
    return await ask_read(settings, _SYSTEM, line, conversation, PosedPick, max_tokens=_MAX_TOKENS)


def may_refer_to_a_problem(line: str, recent: Sequence[Any], *, claimed: bool = False) -> bool:
    """A cheap look on the loop: a short line right after a reply. ``claimed``: a subject
    claims the line but reads no problem in it, so only a line that states a value may
    change one, and it may be longer."""
    words = collapse_ws(line).split()
    if claimed:
        if len(words) > _MAX_RESTATED_WORDS or not _STATES_A_VALUE.search(line):
            return False
    elif not words or len(words) > _MAX_WORDS:
        return False
    exchanges = chat_before(recent, line)
    return bool(exchanges) and exchanges[-1][0] == "assistant"


_KEPT = "posed"


def _key(
    line: str, recent: Sequence[Any], claimed: SubjectName | None
) -> tuple[str, tuple[tuple[str, str], ...], SubjectName | None]:
    # Keyed by the chat too: a run of turns outside a request (the sweep) shares one memo.
    # And by the claiming subject: a read for no subject (None) is no answer for physics.
    return line, tuple(chat_before(recent, line)), claimed


async def posed_for_turn(
    settings: Settings, line: str, recent: Sequence[Any], *, claimed: SubjectName | None = None
) -> Posed | None:
    """``read_posed`` once a turn, kept as the other reads are (``core.readings``)."""
    key = _key(line, recent, claimed)
    kept = kept_for_turn(_KEPT)
    if isinstance(kept, tuple) and kept[0] == key:
        posed: Posed | None = kept[1]
        return posed
    posed = await read_posed(settings, line, recent, claimed=claimed)
    keep_for_turn(_KEPT, (key, posed))
    return posed


async def read_posed(
    settings: Settings, line: str, recent: Sequence[Any], *, claimed: SubjectName | None = None
) -> Posed | None:
    """The problem a short line asks to solve or change, as its message states it; None with
    no read, after an exchange that holds no problem, or when the line answers a question
    or asks no solve. ``claimed``: the subject that claims the line, when one does."""
    if not settings.referent_read_enabled or not may_refer_to_a_problem(
        line, recent, claimed=claimed is not None
    ):
        return None
    exchanges = chat_before(recent, line)
    asked = exchanges[-2][1] if len(exchanges) > 1 and exchanges[-2][0] == "user" else None
    # A look the turn can do without: a pool that gives up never declines its readings.
    timeout = settings.subject_read_timeout_seconds
    if claimed is not None:
        held = await read_aside(restates_a_problem, claimed, asked, line, timeout=timeout)
    else:
        held = await read_aside(holds_a_problem, asked, exchanges[-1][1], timeout=timeout)
    if not held:
        return None
    started = time.perf_counter()
    read = await pick_posed(settings, collapse_ws(line), _numbered(exchanges))
    logger.info(
        "posed read took %.0f ms kind=%s changes=%d",
        (time.perf_counter() - started) * 1000,
        read.kind if read is not None else None,
        len(read.changes) if read is not None else 0,
    )
    if read is None or read.kind not in ("solve", "change") or read.message is None:
        return None
    if not 1 <= read.message <= len(exchanges):
        return None
    problem = _stated(*exchanges[read.message - 1], read.problem)
    if problem is None:
        return None
    # A line a subject claims, or one that states values its problem does not, changes the
    # question it follows ("Repeat it with 3.0 pC"): only a change of the asked turn's own
    # problem stands (the user's message the last reply answered, or that reply when it
    # posed one), never "solve" the problem as it was: its card would answer a question
    # the line did not ask.
    # Read in the pool, with every subject's units; a pool that gives up counts as new.
    new = await read_aside(states_new_values, line, problem, timeout=timeout)
    if claimed is not None or new is not False:
        last_turn = {len(exchanges)} | ({len(exchanges) - 1} if asked is not None else set())
        if read.kind != "change" or read.message not in last_turn:
            return None
    if read.kind == "solve":
        return Posed(problem=problem, reply=exchanges[-1][1])
    return Posed(
        problem=problem,
        reply=exchanges[-1][1],
        changed=True,
        changes=tuple(
            (collapse_ws(change.given or "") or None, _line_value(line, change.new))
            for change in read.changes
        ),
    )
