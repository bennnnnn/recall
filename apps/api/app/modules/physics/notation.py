"""The symbols a reply shows for a law that tells a starting velocity from a final one.

A reply writes the letters of its students' textbooks (Ethiopian school physics, British
style): initial velocity u, final velocity v, displacement s and distance d, so
v = u + at, s = ut + ½at² and v² = u² + 2as. The constant-acceleration laws are
written that way in the catalog already. Other laws keep the letters the binder, the
model reader and the solvers name (``v_1`` and ``v_2`` before and after an impulse,
``v_0`` for a launch, whose subscript 0 tells the binder it is a start), and this table
is the one place that decides what the reply shows instead: every row a solver stores
(``working.attach_recorded_working``), and every symbol the direct reply takes from the
catalog (the givens, their meanings, Required, the law's own lines), pass through
``shown``. A law not in the table is shown as written; a plain speed (``v = d/t``) has
no start or end to tell apart.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.modules.physics.catalog.projectile import SPECS as PROJECTILE
from app.modules.physics.catalog.vertical import SPECS as VERTICAL
from app.services.latex_groups import group_end

# One body before and after: an impulse, the work done on it, a bounce off a wall.
_BEFORE_AFTER: Mapping[str, str] = {"v_1": "u", "v_2": "v"}
# Two bodies colliding: each one's velocity before (v_1, v_2) and after (v_1', v_2'),
# and the one velocity of two that stick together (v_f).
_TWO_BODIES: Mapping[str, str] = {
    "v_1": "u_1",
    "v_2": "u_2",
    "v_1'": "v_1",
    "v_2'": "v_2",
    "v_f": "v",
}
# Braking from a speed v to rest: the speed is where the stop starts.
_BRAKING_FROM: Mapping[str, str] = {"v": "u"}
# Thrown up or down, or launched at an angle: the speed it leaves with is u.
_LAUNCH: Mapping[str, str] = {"v_0": "u"}

_SHOWN: Mapping[str, Mapping[str, str]] = {
    "impulse": _BEFORE_AFTER,
    "work_energy": _BEFORE_AFTER,
    "momentum_change_rebound": _BEFORE_AFTER,
    "rebound_average_force": _BEFORE_AFTER,
    "final_velocity": _TWO_BODIES,
    "collision_energy_lost": _TWO_BODIES,
    "stopping_distance": _BRAKING_FROM,
    **{spec.id: _LAUNCH for spec in (*VERTICAL, *PROJECTILE)},
}

# Arguments that are words, not symbols: ``\mathrm{m/s}``, ``\text{ before}``.
_WORD_ARGUMENTS = frozenset({"text", "mathrm", "textrm", "operatorname", "mbox"})


def shown(latex: str, operation: str | None) -> str:
    """``latex`` with this law's velocities written as the reply shows them.

    ``I = m(v_2 - v_1)`` becomes ``I = m(v - u)`` and ``v_0 t`` becomes ``u t``; a command
    (``\\tau``, ``\\frac``), a word argument (``\\mathrm{m/s}``) and a number are left
    as they are.
    """
    table = _SHOWN.get(operation or "")
    if not table or not latex:
        return latex
    return _rename(latex, table)


def _rename(latex: str, table: Mapping[str, str]) -> str:
    out: list[str] = []
    at = 0
    while at < len(latex):
        char = latex[at]
        if char == "\\":
            end = _command_end(latex, at)
            out.append(latex[at:end])
            at = end
        elif char.isascii() and char.isalpha():
            end = _symbol_end(latex, at)
            symbol = latex[at:end]
            replacement = table.get(_plain(symbol))
            if replacement is None:
                out.append(symbol)
            else:
                out.append(replacement)
                # "ut" is u times t: v_i t, never the subscript "it".
                if "_" in replacement and end < len(latex) and latex[end].isalnum():
                    out.append(" ")
            at = end
        else:
            out.append(char)
            at += 1
    return "".join(out)


def _command_end(latex: str, start: int) -> int:
    """Past a command, and past its argument when that argument is words."""
    end = start + 1
    while end < len(latex) and latex[end].isascii() and latex[end].isalpha():
        end += 1
    if end == start + 1:
        # A one-character command: "\,", "\ ", "\{".
        return min(end + 1, len(latex))
    if latex[start + 1 : end] in _WORD_ARGUMENTS:
        brace = end
        while brace < len(latex) and latex[brace] == " ":
            brace += 1
        if brace < len(latex) and latex[brace] == "{":
            return group_end(latex, brace)
    return end


def _symbol_end(latex: str, at: int) -> int:
    """Past one symbol: a letter, its subscript (``_1``, ``_{net}``) and any primes."""
    end = at + 1
    if end < len(latex) and latex[end] == "_":
        if end + 1 < len(latex) and latex[end + 1] == "{":
            end = group_end(latex, end + 1)
        elif end + 1 < len(latex) and latex[end + 1] != "\\":
            end += 2
    while end < len(latex) and latex[end] == "'":
        end += 1
    return end


def _plain(symbol: str) -> str:
    """``v_{1}'`` and ``v_1'`` are one symbol."""
    head, _, rest = symbol.partition("_")
    if not rest:
        return symbol
    primes = len(rest) - len(rest.rstrip("'"))
    script = rest.rstrip("'")
    if script.startswith("{") and script.endswith("}") and len(script) == 3:
        script = script[1]
    return f"{head}_{script}" + "'" * primes
