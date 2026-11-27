# ruff: noqa: RUF001, RUF002, RUF003 -- the module reads × and − as replies write them.
"""Each unchecked answer card held to the value its own working's chain reaches.

``working_chain`` works every value of the working again from its own method at full
precision, the arithmetic redone and nothing else, and finds the chain each card states.
When the card's number misses the chain's value by more than its own rounding, the slip
carried into the card (u8-28, 2026-11-26: "\\frac{2.0}{400 \\times 1.0 \\times 10^{-4}}"
worked as 50000, not 50, carded 2.41 × 10⁻⁴ W for 0.241 W), and the card takes the chain's
value; a short note says what was corrected. A card that holds the value only more coarsely
than the rule shows it (56.6 for 56.58) takes the value too, with no note, so the rule rounds
it once (``card_numbers``).

A card stands when it states any value its part worked out (the largest of five
accelerations is no slip of the last), when it is the value's size without its sign, when it
is a count rounded as asked (4 buses for 3.75), or when it is the server's.

When in doubt, nothing changes. A card's unit not read for certain (°C, °, rad/s, %) leaves
the card alone unless its chain writes the very same unit: 126.85 °C under a chain in K is
right. A card ten or a thousand times off its chain is a slip only when both write a unit read
for certain; with no unit on the chain, a card more than 1.5 times off may be the value in a
unit the working never named (3.6, 60, 1000), and stands. A card in another unit than its
chain gets the chain's value in its own unit when Pint reads both, and a chain that writes no
unit is given one only when every given put into its formula is read with its unit and the
formula has no number of its own that could be a conversion ("2πN/60" is left alone).

The card stays unchecked: the server checked arithmetic, not the method.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Any

from pint.errors import PintError

from app.modules.chat.formula_inputs import aligned_names
from app.modules.chat.tex_arithmetic import plain_arithmetic
from app.modules.chat.working_cards import closing_end, counted, repeats, said_again
from app.modules.chat.working_chain import (
    CARRIED_FIGURES,
    CardRead,
    Chain,
    Reading,
    read_chains,
)
from app.modules.chat.working_claims import Claim
from app.modules.chat.working_numbers import shown_number
from app.modules.chat.working_units import (
    converted,
    quantity_unit,
    read_for_certain,
    unit_after,
    with_units,
)
from app.services.rounding_rule import RULE, Precision, number_latex
from app.services.units import get_unit_registry

_POWERS_OF_TEN = tuple(range(1, 13))
# Why a card changed: a slip carried into it, rounding carried, a conversion left out.
SLIP, DRIFT, UNIT = "slip", "drift", "unit"


@dataclass(frozen=True)
class Corrected:
    """One card set to its chain's value: where its number is, what it said, the value."""

    name: str
    start: int
    end: int
    said: str
    shown: str
    unit_tex: str
    # SLIP, DRIFT, UNIT, or "" for a card rounded again (no note).
    kind: str
    # The slip the card carried ("e = \\frac{…}{…}"), "" for none.
    slip: str
    # Where the card's fence body ends.
    body_end: int
    # The reply's last card: the lines after it are its closing summary, nobody's working.
    last: bool = False


@dataclass(frozen=True)
class ChainNotes:
    """The closing lines the chains give: what was corrected, a slip no card carried, and a
    claim the working's own values do not bear out; None for each with nothing to say."""

    corrected: str | None
    slip: str | None
    claim: str | None


def held_to_chains(
    text: str, question: str = "", precision: Precision = RULE
) -> tuple[str, ChainNotes]:
    """``text`` with each card its working's chain contradicts set to the chain's value and
    the wrong value said again after it set the same, and the notes (the module docstring)."""
    reading = read_chains(text, question)
    fixes = [fix for card in reading.cards if (fix := _corrected(card, reading, precision))]
    for fix in reversed(fixes):
        text = _applied(text, fix)
    notes = ChainNotes(
        _corrected_note(fixes), _slip_note(reading.chains), _claim_note(reading.claims)
    )
    return text, notes


def _corrected(card: CardRead, reading: Reading, precision: Precision) -> Corrected | None:
    chain = card.chain
    if chain is None or card.server:
        return None
    card_unit = unit_after(card.unit_tex)
    value, kind = _in_card_unit(chain, card_unit, reading)
    if value is None:
        return None
    plain = plain_arithmetic(card.number.replace("−", "-"))
    shown = shown_number(plain or "", coarse=card.approximate or "." not in card.number)
    if plain is None or shown is None or counted(value, card.number):
        return None
    new = number_latex(value, precision)
    if _holds(shown, value, chain.reach):
        # Held, maybe more coarsely than the rule shows it: the value, rounded once. A whole
        # card claims no places to fill, and a size without its sign is the card's choice.
        coarser = kind != UNIT and _coarse(card.number) and _same_sign(shown[0], value)
        return (
            _fix(card, chain, new, "", "")
            if coarser and new != number_latex(shown[0], precision)
            else None
        )
    slip = _slip_before(reading.chains, chain, card.since)
    kind = kind or (SLIP if slip else DRIFT)
    if kind != UNIT and _states_another(shown, reading.chains, card, chain):
        return None
    if kind == DRIFT and chain.written is not None and _holds(shown, *chain.written):
        # Right on the rounded numbers the working wrote: rounding carried, no slip.
        return None
    if not _units_certain(chain.unit, card_unit) and not _near(shown[0], value):
        # One side writes no unit: a card ten, sixty or 3.6 times off may be the value in a
        # unit the working never named, so only a slip within a factor of 1.5 is certain.
        return None
    return _fix(card, chain, new, kind, slip)


# How far a card may be off a chain with no unit and still be a slip of its own: beyond
# this it may be the value in another unit (×3.6, ×60, ×100, ×1000).
_NEAR = 1.5


def _near(shown: float, value: float) -> bool:
    if shown == 0 or value == 0 or (shown < 0) != (value < 0):
        return False
    ratio = abs(shown / value)
    return 1 / _NEAR <= ratio <= _NEAR


def _units_certain(chain_unit: str, card_unit: str) -> bool:
    """The chain and the card both write a unit, and both are read for certain (or are the
    same text): a card a power of ten off is then a slip, not a prefix."""
    if not chain_unit or not card_unit:
        return False
    return chain_unit == card_unit or (read_for_certain(chain_unit) and read_for_certain(card_unit))


def _fix(card: CardRead, chain: Chain, new: str, kind: str, slip: str) -> Corrected:
    name = chain.label or chain.name
    return Corrected(
        name,
        card.start,
        card.end,
        card.number,
        new,
        card.unit_tex,
        kind,
        slip,
        card.body_end,
        card.last,
    )


def _coarse(number: str) -> bool:
    """A card's number that may be rounded more coarsely than the rule: one with places, or a
    whole number ending in zeros (6200000 for 6238873.77)."""
    return "." in number or (
        number.rstrip("0") != number and len(number.rstrip("0")) < len(number) - 1
    )


def _same_sign(shown: float, value: float) -> bool:
    return (shown < 0) == (value < 0)


def _holds(shown: tuple[float, float], value: float, reach: float) -> bool:
    """The card's number is the value, or its size, within the card's own rounding."""
    slack = (shown[1] + reach) * (1 + 1e-9) + 1e-12 * abs(value)
    return abs(shown[0] - value) <= slack or abs(abs(shown[0]) - abs(value)) <= slack


def _states_another(
    shown: tuple[float, float], chains: list[Chain], card: CardRead, own: Chain
) -> bool:
    """The card states another value its part worked out, to its own rounding: the largest
    of several, a step before the last."""
    part = [chain for chain in chains if card.since <= chain.start < card.start]
    return any(
        not math.isclose(chain.value, own.value, rel_tol=1e-9) and _holds(shown, chain.value, 0.0)
        for chain in part
    )


def _slip_before(chains: list[Chain], chain: Chain, since: int) -> str:
    """The slip a card's value carries: its chain's own, else the last one of a chain worked
    before it in its part ("$K_{rot} = 30.09$" under a card of the sum), as TeX; "" for none."""
    if chain.slip:
        return f"{chain.label or chain.name} = {chain.slip}"
    earlier = [c for c in chains if since <= c.start and c.end <= chain.start and c.slip]
    return f"{earlier[-1].label or earlier[-1].name} = {earlier[-1].slip}" if earlier else ""


def _in_card_unit(chain: Chain, card_unit: str, reading: Reading) -> tuple[float | None, str]:
    """The chain's value in the card's unit, and UNIT when a conversion the working left out
    was put in; None when the two are not one kind, or either unit is not read for certain
    (126.85 °C under a chain in K, 30° under one in rad) and they are not written alike."""
    target = quantity_unit(card_unit) if card_unit else None
    derived = _substituted(chain, reading.givens) if target is not None else None
    if derived is not None and target is not None:
        value = _magnitude_in(derived, target)
        if value is not None and not math.isclose(value, chain.value, rel_tol=1e-9):
            return value, UNIT
    if card_unit == chain.unit or not card_unit:
        return chain.value, ""
    if not read_for_certain(card_unit):
        return None, ""
    if not chain.unit:
        return chain.value, ""
    source = quantity_unit(chain.unit)
    if source is None or target is None:
        return None, ""
    return converted(chain.value, source, target), ""


def _magnitude_in(quantity: Any, unit: Any) -> float | None:
    try:
        return float(quantity.to(unit).magnitude)
    except (PintError, TypeError, ValueError, ArithmeticError):
        return None


def _ten_fold(shown: float, value: float) -> bool:
    """The two are a power of ten apart: a prefixed unit the working may not have named."""
    if shown == 0 or value == 0:
        return False
    ratio = abs(shown / value)
    return any(
        math.isclose(ratio, 10.0**power, rel_tol=0.02)
        or math.isclose(ratio, 10.0**-power, rel_tol=0.02)
        for power in _POWERS_OF_TEN
    )


def _applied(text: str, fix: Corrected) -> str:
    """``text`` with the card's number written again, and the wrong value said again in the
    closing lines after the reply's last card said as the right one: only a number of three
    figures, never one the working wrote before the card too (which mention is the card's is
    unknown)."""
    text = f"{text[: fix.start]}{fix.shown}{text[fix.end :]}"
    plain = plain_arithmetic(fix.said.replace("−", "-")) or fix.said
    figures = len(plain.strip("()-").partition("e")[0].replace(".", "").strip("0"))
    if not fix.kind or not fix.last or figures < CARRIED_FIGURES:
        # Only after the reply's last card: after any other the next part's working starts.
        return text
    wrong = repeats({fix.said, plain})
    if wrong.search(text[: fix.start]) is not None:
        return text
    body_end = fix.body_end + len(fix.shown) - (fix.end - fix.start)
    closing = closing_end(text, body_end)
    tail = said_again(text[body_end:closing], wrong, fix.shown, dropped=False)
    return f"{text[:body_end]}{tail}{text[closing:]}"


def _substituted(chain: Chain, givens: dict[str, tuple[str, str]]) -> Any:
    """The chain's value as a Pint quantity, when its method is its formula with each name a
    given put in and every given read with its unit (the module docstring); else None."""
    names = aligned_names(chain.formula, chain.method) if chain.formula else None
    plain = plain_arithmetic(chain.method)
    if not names or plain is None:
        return None
    registry = get_unit_registry()
    quantities: dict[str, Any] = {}
    for name, number in names.items():
        given = givens.get(name)
        if given is None or given[0] != repr(float(number)):
            return None
        parsed = quantity_unit(given[1]) if given[1] else None
        if given[1] and parsed is None:
            return None
        quantities[number] = registry.Quantity(float(number), parsed or registry.dimensionless)
    try:
        tree = ast.parse(plain, mode="eval")
    except SyntaxError:
        return None
    return with_units(tree.body, plain, quantities)


def _corrected_note(fixes: list[Corrected]) -> str | None:
    """One closing line naming each corrected card and the slip it carried, if any."""
    said = [fix for fix in fixes if fix.kind]
    if not said:
        return None
    values = "; ".join(
        f"${fix.name} = {fix.shown}{fix.unit_tex}$, not ${fix.said}{fix.unit_tex}$" for fix in said
    )
    slips = list(dict.fromkeys(f"${fix.slip}$" for fix in said if fix.kind == SLIP and fix.slip))
    if slips:
        where = " and ".join(slips)
        return (
            f"Corrected: the working slips at {where}. Worked again from its own steps, {values}."
        )
    if any(fix.kind == UNIT for fix in said):
        return f"Corrected: a unit conversion was left out of the working. With it, {values}."
    return f"Corrected: worked again without rounding along the way, {values}."


def _slip_note(chains: list[Chain]) -> str | None:
    """One closing line naming the first slip in the working, with the value its own method
    gives: for a slip no corrected card names."""
    slipped = next((chain for chain in chains if chain.slip), None)
    if slipped is None:
        return None
    name = slipped.label or slipped.name
    unit = f"\\,\\mathrm{{{slipped.unit}}}" if slipped.unit and "*" not in slipped.unit else ""
    return (
        f"Check this step: ${name} = {slipped.slip}$ does not follow from the working; "
        f"worked again, ${name} = {number_latex(slipped.value)}{unit}$."
    )


def _claim_note(claims: list[Claim]) -> str | None:
    """One closing line naming the first claim the working's own values contradict."""
    if not claims:
        return None
    claim = claims[0]
    value = number_latex(claim.value)
    return (
        f"Check: with the working's own values, ${claim.left} = {value}$, not "
        f"${claim.said}$, so these do not agree."
    )
