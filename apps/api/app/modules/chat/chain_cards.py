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
is a count rounded as asked (4 buses for 3.75), or when it is the server's. A card ten, a
thousand or a million times off its chain is a slip only when the working slipped or both
write the same unit: it may be the value in a prefixed unit the working never named.

A card in another unit than its chain gets the chain's value in its own unit, when Pint
reads both. A chain that writes no unit is given one only when it is certain: its method is
its formula with each name a given put in, every given read with its unit, and no number of
the formula's own that could be a conversion ("ω = 2πN" with N = 250 rev/min is 26.18 rad/s,
never 1570.80; "2πN/60" is left alone).

The card stays unchecked: the server checked arithmetic, not the method.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Any

from app.modules.chat.tex_arithmetic import plain_arithmetic
from app.modules.chat.working_cards import closing_end, counted, repeats, said_again
from app.modules.chat.working_chain import (
    CARRIED_FIGURES,
    CardRead,
    Chain,
    Reading,
    aligned_names,
    read_chains,
)
from app.modules.chat.working_claims import Claim
from app.modules.chat.working_numbers import shown_number
from app.modules.chat.working_units import converted, quantity_unit, unit_after
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


def held_to_chains(
    text: str, question: str = "", precision: Precision = RULE
) -> tuple[str, str | None, str | None]:
    """``text`` with each card its working's chain contradicts set to the chain's value and
    the wrong value said again after it set the same; a note naming what was corrected, and
    one naming a claim the working's own values do not bear out (the module docstring)."""
    reading = read_chains(text, question)
    fixes = [fix for card in reading.cards if (fix := _corrected(card, reading, precision))]
    for fix in reversed(fixes):
        text = _applied(text, fix)
    return text, _corrected_note(fixes), _claim_note(reading.claims)


def _corrected(card: CardRead, reading: Reading, precision: Precision) -> Corrected | None:
    chain = card.chain
    if chain is None or card.server:
        return None
    value, kind = _in_card_unit(chain, unit_after(card.unit_tex), reading)
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
    if _ten_fold(shown[0], value) and kind == DRIFT and not chain.unit:
        return None
    return _fix(card, chain, new, kind, slip)


def _fix(card: CardRead, chain: Chain, new: str, kind: str, slip: str) -> Corrected:
    name = chain.label or chain.name
    return Corrected(name, card.start, card.end, card.number, new, card.unit_tex, kind, slip)


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
    """The card states another value its part worked out: the largest of several, a step
    before the last."""
    part = [chain for chain in chains if card.since <= chain.start < card.start]
    return any(chain is not own and _holds(shown, chain.value, chain.reach) for chain in part)


def _slip_before(chains: list[Chain], chain: Chain, since: int) -> str:
    """The slip a card's value carries: its chain's own, else the last one of a chain worked
    before it in its part ("$K_{rot} = 30.09$" under a card of the sum), as TeX; "" for none."""
    if chain.slip:
        return f"{chain.label or chain.name} = {chain.slip}"
    earlier = [c for c in chains if since <= c.start and c.end <= chain.start and c.slip]
    return f"{earlier[-1].label or earlier[-1].name} = {earlier[-1].slip}" if earlier else ""


def _in_card_unit(chain: Chain, card_unit: str, reading: Reading) -> tuple[float | None, str]:
    """The chain's value in the card's unit, and UNIT when a conversion the working left out
    was put in; None when the units are not one kind or cannot be read."""
    target = quantity_unit(card_unit) if card_unit else None
    derived = _substituted(chain, reading.givens) if target is not None else None
    if derived is not None and target is not None:
        value = _magnitude_in(derived, target)
        if value is not None and not math.isclose(value, chain.value, rel_tol=1e-9):
            return value, UNIT
    if not card_unit or not chain.unit:
        return chain.value, ""
    source = quantity_unit(chain.unit)
    if source is None or target is None:
        return (chain.value, "") if card_unit == chain.unit else (None, "")
    return converted(chain.value, source, target), ""


def _magnitude_in(quantity: Any, unit: Any) -> float | None:
    try:
        return float(quantity.to(unit).magnitude)
    except Exception:
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
    closing lines after it said as the right one: only a number of three figures, never one
    the working wrote before the card too (which mention is the card's is unknown)."""
    text = f"{text[: fix.start]}{fix.shown}{text[fix.end :]}"
    plain = plain_arithmetic(fix.said.replace("−", "-")) or fix.said
    figures = len(plain.strip("()-").partition("e")[0].replace(".", "").strip("0"))
    if not fix.kind or figures < CARRIED_FIGURES:
        return text
    wrong = repeats({fix.said, plain})
    if wrong.search(text[: fix.start]) is not None:
        return text
    after = text.find("```", fix.start + len(fix.shown))
    body_end = len(text) if after < 0 else after
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
    return _with_units(tree.body, plain, quantities)


def _with_units(node: ast.AST, plain: str, quantities: dict[str, Any]) -> Any:
    """``node`` worked out with each given as its quantity; None for anything but numbers,
    pi, the four operations, a whole power and a square root."""
    registry = get_unit_registry()
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        written = ast.get_source_segment(plain, node) or ""
        number = registry.Quantity(float(node.value), registry.dimensionless)
        return quantities.get(written, number)
    if isinstance(node, ast.Name) and node.id == "pi":
        return registry.Quantity(math.pi, registry.dimensionless)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _with_units(node.operand, plain, quantities)
        return None if inner is None else -inner
    if isinstance(node, ast.BinOp):
        left = _with_units(node.left, plain, quantities)
        right = _with_units(node.right, plain, quantities)
        return None if left is None or right is None else _operated(node.op, left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sqrt":
        inner = _with_units(node.args[0], plain, quantities) if len(node.args) == 1 else None
        return None if inner is None else inner**0.5
    return None


def _operated(op: ast.operator, left: Any, right: Any) -> Any:
    try:
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.Pow) and right.dimensionless and float(right.magnitude).is_integer():
            return left ** int(right.magnitude)
    except Exception:
        return None
    return None


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
