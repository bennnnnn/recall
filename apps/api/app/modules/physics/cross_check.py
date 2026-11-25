"""A verified physics answer held to a second reading of the question.

The extractors bind a question's values by unit and keyword. Casual wording misleads them
("slowing down at 3 m/s^2" bound as +3 m/s²; "kicked sideways off a 30 m cliff" read as a
fall in one line), and the solver then certifies the wrong reading: three checked wrong
answers in 100 casual rewordings (live QA, 2026-11-22). So every verified answer is held to
the formal reader's reading of the same question (``physics.formal_read``): a model writes
it down as maths, in any wording, and the server solves that setup. Two readings that agree
keep the check; a solved reading that differs leaves the question to the model, unverified,
because a solver value is never stamped over a reading that contradicts it. A reading the
server could not solve holds nothing on its own; when its model's own arithmetic disagrees,
a second reader is asked (``cross_check``).

Each value the reading asks for comes with the server's value for it (across the band the
standard constants allow, g as 9.8 or 10) and the setup's own answer; the solver's values
are paired with them by kind (pint's dimensionality), in any unit of the kind ("72 km/h" is
20 m/s), by size (a sign is a direction's), within ``AGREEMENT``. Within each kind the
smaller side must be covered by the larger: a card may show more than was asked (both balls'
speeds after a collision), and a partial solve answers less than the reading asks.

- ``agree``: every kind both sides hold is covered so.
- ``disagree``: a kind is not, or the two share no kind (the reading asked another
  quantity: it read another question).
- ``unread``: no reading to hold it to: none in ``formal_wait_seconds``, a failed or capped
  read, a setup that asks no value, or units neither side can read. The check stands, as it
  did before: every such answer measured was right (all late reads), and dropping them removed
  no wrong one (``app/tests/behavior/cross_check_eval.py``, docs/FORMAL_READER.md). A setup the
  server could not solve is ``unread`` too (the reading model's own arithmetic alone is no
  reading), but only once its doubt, if it raises one, has had a second reader
  (``cross_check``): alone, it let one wrong answer of 422 through.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from app.core.aio import settled_result
from app.core.config import Settings
from app.services.solving import VerifiedPhysicsBlock

logger = logging.getLogger(__name__)

Verdict = Literal["agree", "disagree", "unread"]

# The reading and the solver agree within this share of the value. Twice ``formal.solve``'s
# 1%: a setup's textbook constants (h as 6.63e-34, g as 9.8), carried through a difference,
# move a right value by 1-2% (0.77 eV for 0.759 eV), and every misreading measured moved it
# by far more (-4 m/s for 20 m/s, 15 m/s for 19.6 m/s, 54 m for 36 m).
AGREEMENT = 0.02


@dataclass(frozen=True)
class ReadAsk:
    """One value the reading asks for: its unit, and the sizes it gives for it, each a range
    (the server's value across its constants' band, and the setup's own answer)."""

    unit: str
    values: tuple[tuple[float, float], ...]


def solver_answers(block: VerifiedPhysicsBlock) -> list[tuple[float, str]]:
    """Each value the block's cards show, unrounded, with its unit."""
    if block.physics_parts:
        pairs = [
            (value, unit)
            for part in block.physics_parts
            for value, unit in zip(part.answer_values, part.answer_units, strict=False)
        ]
    else:
        pairs = list(zip(block.answer_values, block.answer_units, strict=False))
    return [(value, unit) for value, unit in pairs if math.isfinite(value)]


def reading_asks(setup: Any, result: dict[str, Any], *, guesses: bool = False) -> list[ReadAsk]:
    """Each value the setup asks for that the server solved, with the server's value for it
    and the setup's own answer.

    Only a value the server worked out is a reading. A setup the server could not solve ("no
    setup", "no real solution"), or an ask it left unsolved, holds only the reading model's
    own arithmetic, and that alone never takes a checked answer away: a reader's guess of
    4.22 s for a cliff throw the solver had right at 4.82 s dropped the check on two of four
    live turns (owner's test, 2026-11-23). The setup's own answer still counts beside the
    server's, so a right setup whose constants differ (g as 9.8 or 10) agrees.

    ``guesses``: the model's own answers count on their own too. Only a doubt is read so,
    never a verdict: it decides whether a second reader is asked (``cross_check``)."""
    solved = result.get("answers") or [] if result.get("solved") else []
    server = {(answer.get("part"), answer.get("symbol")): answer for answer in solved}
    asks: list[ReadAsk] = []
    for asked in setup.asked:
        values: list[tuple[float, float]] = []
        answer = server.get((asked.part, asked.symbol))
        if answer is not None:
            ends = (float(answer["low"]), float(answer["high"]), float(answer["value"]))
            values.append((min(ends), max(ends)))
        elif not guesses:
            continue
        if asked.answer is not None and math.isfinite(asked.answer):
            values.append((asked.answer, asked.answer))
        if values:
            asks.append(ReadAsk(asked.unit, tuple(values)))
    return asks


# An angle is its own kind, though pint reads it as a plain number: 30° is no ratio.
_ANGLE = re.compile(r"deg(?!ree_?[cf]|[cf])|°(?!\s*[cf])|\brad", re.IGNORECASE)
# A temperature unit, which may be a change ("10 K" warmer is "10 °C" warmer) or a reading.
_TEMPERATURE = {"degC": "delta_degC", "°C": "delta_degC", "degF": "delta_degF", "°F": "delta_degF"}


def _kind(unit: str) -> Any | None:
    from app.services.formal.maths import as_quantity

    try:
        kind = as_quantity(1.0, unit).dimensionality
    except Exception as exc:  # pint: a unit it cannot read has no kind to compare by
        logger.info("physics cross-check: a unit not read (%s)", type(exc).__name__)
        return None
    return ("angle", str(kind)) if _ANGLE.search(unit) else kind


def _readings_of(unit: str, target: str) -> list[tuple[str, str]]:
    """The ways to read ``unit`` in ``target``: as it is, and for a temperature also as a
    change (a 10 K rise is a 10 °C rise, though 10 K is no 10 °C reading)."""
    change = (_TEMPERATURE.get(unit, unit), _TEMPERATURE.get(target, target))
    return [(unit, target)] + ([change] if change != (unit, target) else [])


def _in_unit(value: float, unit: str, target: str) -> float | None:
    from app.services.formal.maths import as_quantity

    try:
        return float(as_quantity(value, unit).to(as_quantity(1.0, target).units).magnitude)
    except Exception as exc:  # pint: an offset unit or one it cannot read
        logger.info("physics cross-check: a unit not converted (%s)", type(exc).__name__)
        return None


def _equals(answer: tuple[float, str], ask: ReadAsk) -> bool:
    """The solver's value is one the reading gives for the ask, by size."""
    value, unit = answer
    size = abs(value)
    for source, goal in _readings_of(ask.unit, unit):
        for low_read, high_read in ask.values:
            low, high = _in_unit(low_read, source, goal), _in_unit(high_read, source, goal)
            if low is None or high is None:
                continue
            bottom, top = sorted((abs(low), abs(high)))
            if min(low, high) < 0 < max(low, high):  # a band across zero holds smaller sizes
                bottom = 0.0
            slack = AGREEMENT * max(size, top) + 1e-12
            if bottom - slack <= size <= top + slack:
                return True
    return False


def unsolved_units(setup: Any, result: dict[str, Any]) -> list[str]:
    """The unit of each value the setup asks for that the server did not solve."""
    solved = result.get("answers") or [] if result.get("solved") else []
    server = {(answer.get("part"), answer.get("symbol")) for answer in solved}
    return [asked.unit for asked in setup.asked if (asked.part, asked.symbol) not in server]


def verdict(
    answers: Iterable[tuple[float, str]],
    asks: Iterable[ReadAsk],
    *,
    unsolved: Iterable[str] = (),
) -> Verdict:
    """How the solver's answers stand against the reading's (module docstring).

    ``unsolved``: the units of the values the reading asked for that the server left
    unsolved. A kind the solver answered that the reading asked but could not solve is no
    other question read: with nothing else of its kind, the answer stands unread (a partial
    solve that worked out the distance but not the time never drops the time)."""
    read: dict[Any, list[ReadAsk]] = {}
    for ask in asks:
        kind = _kind(ask.unit)
        if kind is not None:
            read.setdefault(kind, []).append(ask)
    solved: dict[Any, list[tuple[float, str]]] = {}
    for answer in answers:
        kind = _kind(answer[1])
        if kind is not None:
            solved.setdefault(kind, []).append(answer)
    if not read or not solved:
        return "unread"
    shared = [kind for kind in solved if kind in read]
    if not shared:
        left = {_kind(unit) for unit in unsolved}
        if any(kind in left for kind in solved):
            return "unread"  # its own kind was asked, the server could not solve it
        return "disagree"  # the reading asks another quantity: it read another question
    for kind in shared:
        values, kind_asks = solved[kind], read[kind]
        # The smaller side is covered by the larger: a card may show more than was asked
        # (both balls' speeds), and a partial solve answers less than the reading asks.
        if len(kind_asks) <= len(values):
            covered = all(any(_equals(v, ask) for v in values) for ask in kind_asks)
        else:
            covered = all(any(_equals(v, ask) for ask in kind_asks) for v in values)
        if not covered:
            return "disagree"
    return "agree"


def start_reading(question: str, settings: Settings) -> asyncio.Task[Any]:
    """The first reader's reading of ``question``, started beside the solve it will hold:
    the check then waits only on what is left of it, not on the solve and then the read."""
    from app.models.routing_lanes import ROUTING
    from app.modules.physics.formal_read import formal_reading

    return asyncio.create_task(
        formal_reading(question, settings, model_alias=ROUTING.physics_setup)
    )


def drop_reading(task: asyncio.Task[Any] | None) -> None:
    """A reading started early that nothing waits on any more: stopped, its error read."""
    if task is not None and not task.done():
        task.cancel()
        task.add_done_callback(lambda done: done.cancelled() or done.exception())


async def _reading_in_time(
    question: str, settings: Settings, alias: str, under_way: asyncio.Task[Any] | None = None
) -> Any | None:
    """One reader's formal reading of ``question``, or None after ``formal_wait_seconds``
    (``under_way``: the reading, already started)."""
    from app.modules.physics.formal_read import formal_reading

    task = under_way or asyncio.create_task(formal_reading(question, settings, model_alias=alias))
    try:
        # Waited on, never awaited: a reading still out when the wait ends is no reading.
        await asyncio.wait([task], timeout=settings.formal_wait_seconds)
    finally:
        if not task.done():  # out of time, or the turn itself was stopped
            task.cancel()
            # A reading that fails while it is being stopped is no reading either; its
            # error is read here so asyncio never reports it as unretrieved (review, #2533).
            task.add_done_callback(lambda done: done.cancelled() or done.exception())
    return settled_result(task)  # None for a reading still out, failed or stopped


def _solved_verdict(answers: list[tuple[float, str]], reading: Any) -> Verdict:
    """The verdict on what the server solved of ``reading`` alone."""
    return verdict(
        answers,
        reading_asks(reading.setup, reading.result),
        unsolved=unsolved_units(reading.setup, reading.result),
    )


async def cross_check(
    block: VerifiedPhysicsBlock,
    question: str,
    settings: Settings,
    *,
    under_way: asyncio.Task[Any] | None = None,
) -> Verdict:
    """The block held to a reading of ``question`` the server solved (module docstring).

    One reader, as a rule. Only when the server could not solve its setup and the reader's own
    arithmetic disagrees is a second reader, from another company, asked after it (each waited
    on at most ``formal_wait_seconds``, so a turn with a doubt, about 2% of them, waits up to
    twice that): that doubt alone never drops a check, a second solved reading against it
    does. Measured on 422 casual questions' kept readings: 273 right
    checks kept and no wrong one, with a second read on 5 of 279 checked answers
    (``cross_check_eval``, 2026-11-23); always reading twice kept 271, the guess counting
    alone 269."""
    answers = solver_answers(block)
    if not answers or not question.strip():
        return "unread"
    from app.models.routing_lanes import ROUTING

    started = time.monotonic()
    found: Verdict = "unread"
    how = "no reading in time"
    reading = await _reading_in_time(question, settings, ROUTING.physics_setup, under_way)
    if reading is not None:
        found = _solved_verdict(answers, reading)
        how = "first reading"
        doubt = verdict(answers, reading_asks(reading.setup, reading.result, guesses=True))
        if found == "unread" and doubt == "disagree":
            second = await _reading_in_time(question, settings, ROUTING.physics_setup_second)
            if second is not None:
                found = _solved_verdict(answers, second)
            how = "second reading, the first unsolved"
    logger.info("physics cross-check: %s after %.2f s (%s)", found, time.monotonic() - started, how)
    return found


def cross_check_on(settings: Settings) -> bool:
    return bool(
        settings.physics_cross_check_enabled
        and settings.formal_reader_enabled
        and settings.physics_enabled
    )
