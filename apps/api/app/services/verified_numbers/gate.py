"""Every count and number a question states is read by its verified card, or the card is
dropped.

A card that ignores what the question states answers another question: "twenty 60 W
bulbs" answered one bulb's energy, "both of the resistors are 10 Ω" one resistor's current,
"the total mass of 2 moles of NaCl and 3 moles of water" the salt alone (2026-10-31,
reviews of #2172 and #2178). The gate compares quantities, never bare magnitudes: a value
with its dimension and, for a count, the quantity each counted item has.

A count holds the card to it only when its items each have a value: written inside the
count ("thirty 60 W bulbs"), said with "each", or the items' own attribute or rate ("both
of my phones charge at 20 W", "the bulbs are rated 60 W"). A value of another noun ("a 50
kg box"), one the sentence calls a total ("with a total force of 200 N"), or a question
that asks about one item ("the energy used by each bulb") does not. Such a count is read
when its items' value is bound once per item (R1 = R2 = 10 Ω for "two 10 Ω resistors"),
when that many values of its kind are listed and read ("4 Ω, 6 Ω and 10 Ω"), or when the
count is an input itself ("seven notebooks"). A vague count of valued items ("several 60 W
bulbs") never reads. Labels (exercise numbers, years, "carbon-14", "[A]0") are no values.
A number no float holds fails the check.

The check runs in the SymPy pool (it reads the message, CLAUDE.md rule 7), with every
pattern bounded. Any failure drops the card, and the model answers, as for any question no
solver reads; nothing here raises into a turn. An experiment behind
``verified_numbers_gate`` ("off"; "counts" holds counts, "all" every number too).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from app.core.config import Settings
from app.services.solving import VerifiedSolveBlock
from app.services.verified_numbers.counts import (
    COUNT,
    VAGUE,
    asks_one_item,
    count_read,
    count_value,
    each_value,
    items,
)
from app.services.verified_numbers.numbers import (
    FRACTION,
    Quantity,
    is_read,
    leaves,
    measured,
    numbers_in,
    stated_quantities,
    to_plain,
)

logger = logging.getLogger(__name__)

Gate = Literal["off", "counts", "all"]
# The check reads one message: it has this long in the pool.
_CHECK_SECONDS = 2.0
# A message longer than this is not read: the card is dropped, the model answers.
_MAX_QUESTION = 4000


@dataclass(frozen=True, slots=True)
class ReadInputs:
    """What a solve read, as plain data the pool can take: the intent's values with their
    units, and the block's text without its answer."""

    subject: str
    measured: tuple[tuple[float, str], ...] = ()
    strings: tuple[str, ...] = ()
    numbers: tuple[float, ...] = ()
    loose_text: str = ""


@dataclass(frozen=True, slots=True)
class GateResult:
    """Whether a card stands, and what it missed: kinds only ("count", "number"), never
    the question's words."""

    stands: bool
    missed: tuple[str, ...] = field(default_factory=tuple)


def read_inputs(verified: VerifiedSolveBlock) -> ReadInputs:
    """What the solve read, never its result (a "2 m/s²" answer is no reading of "two
    horses"): the physics law's inputs, the chemistry intent, or the block's text without
    its answer. A maths block keeps no intent; the pool reads the question's again."""
    measured: list[tuple[float, str]] = []
    strings: list[str] = []
    numbers: list[float] = []
    physics = getattr(verified, "physics_intent", None)
    if physics is not None:
        units = physics.physics_units or {}
        measured += [(v, units.get(k, "")) for k, v in (physics.physics_params or {}).items()]
        for part in getattr(verified, "physics_parts", ()):
            strings += list(part.substitutions)
    chemistry: Any = getattr(verified, "intent", None)
    if chemistry is not None:
        units = getattr(chemistry, "units", None) or {}
        params = getattr(chemistry, "params", None) or {}
        measured += [(value, units.get(key, "")) for key, value in params.items()]
        rest = chemistry.model_dump(mode="json", exclude_none=True, exclude={"params", "units"})
        for leaf in leaves(rest):
            if isinstance(leaf, str):
                strings.append(leaf)
            elif math.isfinite(leaf):
                numbers.append(float(leaf))
    loose = ""
    if physics is None and chemistry is None and verified.subject != "math":
        loose = verified.text
        for answer in (verified.canonical_answer, verified.display_answer):
            if answer:
                loose = loose.replace(answer, " ")
    return ReadInputs(verified.subject, tuple(measured), tuple(strings), tuple(numbers), loose)


def read_quantities(question: str, inputs: ReadInputs) -> list[Quantity]:
    read = [measured(value, unit) for value, unit in inputs.measured]
    read += [Quantity(value) for value in inputs.numbers]
    read += [Quantity(value) for text in inputs.strings for value in numbers_in(text)]
    read += [Quantity(value) for value in numbers_in(inputs.loose_text)]
    if inputs.subject == "math":
        from app.modules.math.tools.extract import extract_math_intent

        intent = extract_math_intent(question)
        if intent is not None:
            for leaf in leaves(intent.model_dump(mode="json")):
                values = numbers_in(leaf) if isinstance(leaf, str) else iter([float(leaf)])
                read += [Quantity(value) for value in values if math.isfinite(value)]
    return read


def check(question: str, inputs: ReadInputs, gate: Gate) -> GateResult:
    """The gate's check, pure: what of ``question`` the read missed."""
    if len(question) > _MAX_QUESTION:
        return GateResult(False, ("long",))
    plain = to_plain(question)
    read = read_quantities(question, inputs)
    stated, unheld = stated_quantities(plain)
    missed = list(unheld)
    counts = [
        (match, value)
        for match in items(plain, COUNT)
        if (value := count_value(match.group("count"))) and value >= 2
    ]
    count_starts = {match.start("count") for match, _ in counts}
    if gate == "all":
        fractions = {
            span
            for found in FRACTION.finditer(plain)
            for span in (found.span(1), found.span(2))
            if is_read(Quantity(int(found.group(1)) / max(int(found.group(2)), 1)), read)
        }
        missed += [
            "number"
            for item in stated
            if item.start not in count_starts
            and (item.start, item.end) not in fractions
            and not is_read(item, read)
        ]
    missed += [
        "count" for match, count in counts if not count_read(plain, match, count, stated, read)
    ]
    missed += [
        "vague"
        for match in items(plain, VAGUE)
        if each_value(plain, match, stated) is not None
        and not asks_one_item(plain, match.group("noun"))
    ]
    return GateResult(not missed, tuple(missed))


async def gate_card(
    question: str, verified: VerifiedSolveBlock | None, settings: Settings
) -> GateResult:
    """Whether a verified card stands under ``verified_numbers_gate``. The check runs in
    the SymPy pool; one that fails or times out drops the card (logged with kinds only),
    and nothing raises into the turn."""
    gate: Gate = settings.verified_numbers_gate
    if gate == "off" or verified is None:
        return GateResult(True)
    from app.core.sympy_executor import run_sympy

    try:
        result = await run_sympy(
            check, question, read_inputs(verified), gate, timeout=_CHECK_SECONDS
        )
    except Exception as exc:
        logger.info(
            "verified-number gate (%s) dropped a card it could not check (%s)",
            gate,
            type(exc).__name__,
        )
        return GateResult(False, ("error",))
    if not result.stands:
        # Kinds and a count only: never the question's words.
        logger.info(
            "verified-number gate (%s) dropped a card: %d unread (%s)",
            gate,
            len(result.missed),
            ",".join(sorted(set(result.missed))),
        )
    return result


async def gate_augmentation(
    augmentation: Any, question: str, settings: Settings, *, image: bool
) -> Any:
    """The dispatcher's result, or the same without its card when the gate drops it (a card
    that ignores a stated count or number answers another question). ``question`` is the
    text the solve read: a maths follow-up's problem, not the follow-up line."""
    if image:
        return augmentation
    gated = await gate_card(question, augmentation.verified, settings)
    if gated.stands:
        return augmentation
    return replace(augmentation, prompt_block=None, verified=None, gate_missed=gated.missed)
