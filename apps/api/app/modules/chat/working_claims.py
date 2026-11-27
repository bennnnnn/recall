"""A claim the working makes in names that its own values contradict.

"Energy check: … giving $\\tfrac{1}{2}mv_5^2 = 405.5$ J, the same as the kinematics value"
(live, 2026-11-27): with the working's own m = 10 kg and v₅ = 5.66 m/s, ½mv₅² is 160.3 J,
so the two do not agree and the check says nothing. A side written only in names and simple
factors (½, 2, π, powers), each name with one value in the working, said to equal a number,
is worked out with those values; when it is another number by more than the slack a rounding
chain has, it is a claim the working does not bear out.

An equation solved for its unknown is no claim: a name that a statement of numbers is
solved for ("2.8 = 1.1 + 0.05F", "19.6H = 156.25") takes its value from that equation, so
no claim is held to it, and a side with a number of its own (1.1 - 0.05F) is an equation, not
a formula. Pure: no IO; nothing is eval-ed.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Callable
from dataclasses import dataclass

from app.modules.chat.tex_arithmetic import evaluate, math_statement_spans, plain_arithmetic
from app.modules.chat.working_check import NAME, statement_parts
from app.modules.chat.working_numbers import shown_number

# The Greek letters a name may be; any other command (\frac, \times, \sqrt) is maths.
_GREEK = frozenset(
    "alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu "
    "xi pi rho sigma tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Sigma Phi "
    "Psi Omega".split()
)
# A number, a space, then a letter: "5 m" writes a unit, never a product of names.
_NUMBER_THEN_LETTER = re.compile(r"\d\s+[A-Za-z]")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# A unit or a word in upright type: no names of the working's.
_UPRIGHT = re.compile(r"\\(?:text|mathrm|textrm|rm|operatorname)\s*\{[^{}]*\}")
# The numbers a formula in names may hold of its own: a count or a simple factor (½mv², 2πr).
_PURE_FACTOR = 4
# A claim is held to the slack a rounding chain has: it is said in prose, not worked out.
_CLAIM_SLACK = 0.01


@dataclass(frozen=True)
class Claim:
    """A side in names said to equal a number ("\\tfrac{1}{2}mv_5^2 = 405.5") that the
    working's own values of those names make another: ``value``."""

    left: str
    said: str
    value: float


def claims_in(parts: list[str], known: Callable[[str], float | None]) -> list[Claim]:
    """Each side of a statement written in names said to equal the number after it, when
    the working's values of every name (``known``) make it another number."""
    found: list[Claim] = []
    for left, right in itertools.pairwise(parts):
        said_plain = plain_arithmetic(right.strip())
        said = shown_number(said_plain) if said_plain is not None else None
        value = _in_names(left.strip(), known)
        if said is None or value is None:
            continue
        slack = max(said[1], _CLAIM_SLACK * max(abs(value), abs(said[0])))
        if abs(value - said[0]) > slack * (1 + 1e-9):
            found.append(Claim(left.strip(), right.strip(), value))
    return found


def _in_names(tex: str, known: Callable[[str], float | None]) -> float | None:
    """A side written in names worked out with the working's one value of each; None when
    it holds no name, a name with no single value, a number of its own, a unit or a word."""
    if _NUMBER_THEN_LETTER.search(tex) or _UPRIGHT.search(tex):
        return None
    names = names_in(tex)
    if not names or any(not _pure(number) for number in _NUMBER.findall(_without(tex, names))):
        return None
    pieces: list[str] = []
    at = 0
    for match in names:
        value = known(plain_name(match.group(0)))
        if value is None:
            return None
        pieces += [tex[at : match.start()], f"({value!r})"]
        at = match.end()
    plain = plain_arithmetic("".join([*pieces, tex[at:]]))
    return evaluate(plain) if plain is not None else None


def solved_for(reply: str) -> set[str]:
    """Every name an equation of numbers is solved for: a statement of no single name whose
    sides mix names and numbers other than simple factors ("2.8 = 1.1 + 0.05F", "19.6H =
    156.25"). Its value comes from that equation, so no claim is held to it."""
    unknowns: set[str] = set()
    for segment, _follows, _at in math_statement_spans(reply):
        parts, _starts = statement_parts(segment, 0)
        if len(parts) < 2 or NAME.fullmatch(parts[0].replace(" ", "")):
            continue
        for part in parts:
            bare = _UPRIGHT.sub(" ", part)
            names = names_in(bare)
            if names and any(not _pure(n) for n in _NUMBER.findall(_without(bare, names))):
                unknowns.update(plain_name(match.group(0)) for match in names)
    return unknowns


def _pure(number: str) -> bool:
    return "." not in number and int(number) <= _PURE_FACTOR


def names_in(tex: str) -> list[re.Match[str]]:
    """The names a side writes, never a command of maths (\\frac, \\times)."""
    return [
        match
        for match in NAME.finditer(tex)
        if not match.group(0).startswith("\\") or match.group(0)[1:].split("_")[0] in _GREEK
    ]


def _without(tex: str, names: list[re.Match[str]]) -> str:
    """``tex`` with its names blanked: their subscripts' digits are no numbers."""
    for match in reversed(names):
        tex = f"{tex[: match.start()]} {tex[match.end() :]}"
    return tex


def plain_name(tex: str) -> str:
    """A name without its spacing, braces and upright wrapper: "K_{\\text{rot}}" is K_rot."""
    compact = re.sub(r"\\(?:text|mathrm)\{([^{}]*)\}", r"\1", tex.replace(" ", ""))
    return compact.replace("{", "").replace("}", "")
