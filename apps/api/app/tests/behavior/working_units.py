"""Whether a worked reply's Substitution shows a given's value without its unit.

A worked answer substitutes its givens with their units (``a = \\frac{48\\,\\mathrm{m/s} -
8\\,\\mathrm{m/s}}{10\\,\\mathrm{s}}``, ``n = 4 g / 2.016 g/mol``). A line that writes a
given's number bare, with no labelled copy of that number beside it, dropped the unit:
``a = \\frac{48 - 8}{10}`` (2026-11-10). A number equal to a given that sits beside a
labelled one is the law's factor (``0.5 \\times 0.5\\,\\mathrm{H}``), and a number inside a
logarithm or the ICE quadratic is a pure number by convention, so neither counts.
"""

from __future__ import annotations

import re

# A given row: "$m = 0.25\,\mathrm{kg}$", or its SI value after a conversion
# ("$T_1 = 20\,^\circ\mathrm{C} = 293.15\,\mathrm{K}$").
_GIVEN = re.compile(
    r"^\$[^$=]+=\s*(?:.*=\s*)?(?P<number>-?\d+(?:\.\d+)?)"
    r"(?:\s*\\times\s*10\^\{(?P<power>-?\d+)\})?\\,(?:\\mathrm\{(?P<unit>[^}]+)\}|\\Omega)",
    re.MULTILINE,
)
# A unit written after a number, as maths or as a chemistry row's text.
_UNIT_AFTER = (
    r"\\,\\mathrm|\\,\\Omega|\^\\circ|\\,\\%|\s*\\%"
    r"|\s?(?:g|mg|kg|mol|L|mL|atm|K|°C|kPa|Pa|mmHg|J|kJ|s|min|h|A|V|M|C)\b"
)
_NUMBER = re.compile(
    r"(?<![\w.^{_])(?P<number>-?\d+(?:\.\d+)?)(?:\s*\\times\s*10\^\{(?P<power>-?\d+)\})?"
    rf"(?P<unit>{_UNIT_AFTER})?"
)
# Pure numbers by convention: a logarithm's argument, an exponential's, the ICE quadratic.
_PURE = re.compile(r"\\(?:log|ln|exp)(?:_\{?\d+\}?)?\s*\([^()]*\)|^\$x = ")


def _value(match: re.Match[str]) -> float:
    value = float(match.group("number"))
    return value * 10.0 ** int(match.group("power")) if match.group("power") else value


def _same(value: float, other: float) -> bool:
    return abs(value - other) <= 1e-6 * max(1.0, abs(other))


def bare_given_lines(reply: str) -> list[str]:
    """The Substitution lines that write a given's number without its unit."""
    if "**Substitution**" not in reply:
        return []
    given = reply.split("**Required**", 1)[0]
    values = [_value(match) for match in _GIVEN.finditer(given) if match.group("unit") != "°"]
    section = reply.split("**Substitution**", 1)[1].split("**Answer", 1)[0]
    bare: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("$") or _PURE.match(line):
            continue
        written = _PURE.sub(" ", line.split("=", 1)[-1])
        numbers = list(_NUMBER.finditer(written))
        labelled = [_value(match) for match in numbers if match.group("unit")]
        for match in numbers:
            value = _value(match)
            if match.group("unit") or value == 0:
                continue
            if any(_same(value, given) for given in values) and not any(
                _same(value, shown) for shown in labelled
            ):
                bare.append(line)
                break
    return bare
