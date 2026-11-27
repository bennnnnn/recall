# ruff: noqa: RUF001, RUF002, RUF003 -- the module reads × and − as replies write them.
"""Each unchecked answer card held to the value its own working's chain reaches.

``working_chain`` works every value of the working again from its own method at full
precision, the arithmetic redone and nothing else, and finds the chain each card states.
When the card's number misses the chain's value by more than its own rounding, the slip
carried into the card (u8-28, 2026-11-26: "\\frac{2.0}{400 \\times 1.0 \\times 10^{-4}}"
worked as 50000, not 50, carded 2.41 × 10⁻⁴ W for 0.241 W), and the card takes the chain's
value; a short note says what was corrected. A card that holds the value only more coarsely
than the rule shows it (56.6 for 56.58) takes the value too, with no note, so the rule rounds
it once (``card_numbers``): only when the chain knows the value more finely than the card,
and only under the rule's own precision, never one the question asks for.

When in doubt, nothing changes. A card and its chain are compared only when the card writes
exactly the unit its chain last wrote (the same unit, the same prefix), read for certain, or
neither writes one: a card in kJ under a chain in J, in °C under one in K, or in rad/s, %
or rev/min, stands. No unit is ever converted. A card stands too when it states another
value its part worked out (the largest of five accelerations is no slip of the last), its
size without the sign, a count rounded as asked (4 buses for 3.75), or the server's value;
and with no unit on either, when it is more than 1.5 times off, which may be a unit the
working never named.

The card stays unchecked: the server checked arithmetic, not the method.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.modules.chat.tex_arithmetic import plain_arithmetic
from app.modules.chat.working_cards import closing_end, counted, repeats, said_again
from app.modules.chat.working_chain import (
    CARRIED_FIGURES,
    CardRead,
    Chain,
    Reading,
    near,
    read_chains,
)
from app.modules.chat.working_claims import Claim
from app.modules.chat.working_numbers import shown_like, shown_number
from app.modules.chat.working_units import quantity_unit, unit_after
from app.services.rounding_rule import RULE, Precision, number_latex

# Why a card changed: a slip carried into it, or rounding carried.
SLIP, DRIFT = "slip", "drift"


@dataclass(frozen=True)
class Corrected:
    """One card set to its chain's value: where its number is, what it said, the value."""

    name: str
    start: int
    end: int
    said: str
    shown: str
    unit_tex: str
    # SLIP, DRIFT, or "" for a card rounded again (no note).
    kind: str
    # The slip the card carried ("e = \\frac{…}{…}"), "" for none.
    slip: str
    # Where the card's fence body ends.
    body_end: int
    # The reply's last card: the lines after it are its closing summary, nobody's working.
    last: bool = False
    # The chain's value: the closing prose writes it in its own notation.
    value: float = 0.0


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
    if chain is None or card.server or not _one_unit(chain.unit, unit_after(card.unit_tex)):
        return None
    value = chain.value
    plain = plain_arithmetic(card.number.replace("−", "-"))
    shown = shown_number(plain or "", coarse=card.approximate or "." not in card.number)
    if plain is None or shown is None or counted(value, card.number):
        return None
    if _holds(shown, value, chain.reach):
        return _rounded_again(card, chain, shown, precision)
    slip = _slip_before(reading.chains, chain, card.since)
    kind = SLIP if slip else DRIFT
    if _states_another(shown, reading.chains, card, chain):
        return None
    if kind == DRIFT and chain.written is not None and _holds(shown, *chain.written):
        # Right on the rounded numbers the working wrote: rounding carried, no slip.
        return None
    if not chain.unit and not near(shown[0], value):
        # No unit on either: a card ten, sixty or 3.6 times off may be the value in a unit the
        # working never named, so only a slip within a factor of 1.5 is certain.
        return None
    return _fix(card, chain, _written(value, card.number, precision), kind, slip)


def _one_unit(chain_unit: str, card_unit: str) -> bool:
    """The card writes the unit its chain last wrote, read for certain, or neither writes one."""
    if chain_unit != card_unit:
        return False
    return not card_unit or quantity_unit(card_unit) is not None


def _rounded_again(
    card: CardRead, chain: Chain, shown: tuple[float, float], precision: Precision
) -> Corrected | None:
    """A card that holds its chain's value more coarsely than the rule shows it takes the
    value, with no note, so the rule rounds it once: only under the rule's own precision, a
    card with places or zeros to fill, and a chain that knows the value more finely."""
    if precision != RULE or not _coarse(card.number) or (shown[0] < 0) != (chain.value < 0):
        return None
    if not math.isfinite(chain.reach) or chain.reach >= shown[1]:
        return None
    new = number_latex(chain.value)
    if new == number_latex(shown[0]):
        return None
    return _fix(card, chain, new, "", "")


def _written(value: float, number: str, precision: Precision) -> str:
    """The corrected card's number: by the rule, or to the card's own places when the
    question asks for a precision the rule does not settle here (the data's figures)."""
    if precision == RULE:
        return number_latex(value)
    if precision.data:
        return shown_like(value, number)
    return number_latex(value, precision)


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
        chain.value,
    )


def _coarse(number: str) -> bool:
    """A card's number that may be rounded more coarsely than the rule: one with places, or a
    whole number ending in zeros (6200000 for 6238873.77)."""
    return "." in number or (
        number.rstrip("0") != number and len(number.rstrip("0")) < len(number) - 1
    )


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


def _applied(text: str, fix: Corrected) -> str:
    """``text`` with the card's number written again, and the wrong value said again in the
    closing lines after the reply's last card said as the right one, in the prose's own
    notation: only a number of three figures, never one the working wrote before the card
    too (which mention is the card's is unknown)."""
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
    said = shown_like(fix.value, fix.said)
    tail = said_again(text[body_end:closing], wrong, said, dropped=False)
    return f"{text[:body_end]}{tail}{text[closing:]}"


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
    return f"Corrected: worked again without rounding along the way, {values}."


def _slip_note(chains: list[Chain]) -> str | None:
    """One closing line naming the first slip in the working, with the value its own method
    gives: for a slip no corrected card names. A unit not read for certain is left out."""
    slipped = next((chain for chain in chains if chain.slip), None)
    if slipped is None:
        return None
    name = slipped.label or slipped.name
    plain_unit = "*" not in slipped.unit and quantity_unit(slipped.unit) is not None
    unit = f"\\,\\mathrm{{{slipped.unit}}}" if plain_unit else ""
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
