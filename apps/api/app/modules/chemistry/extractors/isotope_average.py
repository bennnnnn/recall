# ruff: noqa: RUF002 -- the weighted sum is written with a multiplication sign.
"""An average atomic mass: isotopes, their abundances, and any mass the question states.

"The atomic masses of the two stable isotopes of boron, ¹⁰B (20%) and ¹¹B (80%) are 10 and
11 respectively" was averaged from the isotope table's 10.0129 u and 11.0093 u (2026-10-31,
an Ethiopian Grade 7 book): a stated mass was read only when written with its unit. A value
the question gives beats the table, however it is given: beside its isotope ("35Cl (34.969 u,
75.77%)", "chlorine-35 has a mass of 34.97"), as a list in the isotopes' order ("are 10 and
11 respectively", "with abundances of 75% and 25%"), or as a table whose header line names
its columns. Only an isotope whose mass the question never states takes the table's.
"""

from __future__ import annotations

import re

from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.extractors.parsing import _N
from app.modules.chemistry.isotopes import ISOTOPE_MASSES
from app.modules.chemistry.schemas import ChemistryIntent
from app.modules.chemistry.species_facts import ELEMENT_NAMES

_AVERAGE_ASK = re.compile(
    r"\b(?:(?:average|relative|mean)\s+)?atomic\s+(?:mass|weight)\b", re.IGNORECASE
)


# "35Cl", "^35Cl", "Cl-35" or "chlorine-35".
_ISOTOPE = re.compile(
    r"(?<![A-Za-z0-9.])(?P<before>\d{1,3})(?P<symbol>[A-Z][a-z]?)(?![a-z])"
    r"|\b(?P<element>[A-Z][a-z]?|[A-Za-z]{3,})-(?P<after>\d{1,3})\b"
)

# Case matters: "235U" is uranium, not 235 u.
_UNIT = r"(?:u|amu|Da)\b"
# "mass" or "masses", never "mass number".
_MASS_WORD = r"(?i:\b(?:atomic\s+|isotopic\s+)?mass(?:es)?\b)(?!\s+(?i:numbers?)\b)"

_ABUNDANCE = re.compile(rf"({_N})\s*%")

# "34.969 u", or a number the text calls a mass: "a mass of 34.97", "with mass 6.015 amu".
_STATED_MASS = re.compile(
    rf"{_MASS_WORD}\s*(?:(?i:of|is|=|:|equal\s+to)\s*)?({_N})(?:\s*{_UNIT})?|({_N})\s*{_UNIT}"
)

# One value of a list, with its percent sign or unit if written.
_ITEM = re.compile(rf"({_N})\s*(%|{_UNIT})?")
# Values for every isotope at once: "10 and 11", "34.97 u, 36.97 u", "75%, 20% and 5%".
_LIST = re.compile(
    rf"(?<![\w.^-]){_ITEM.pattern}(?:\s*(?:,\s*(?:and\s+)?|\s+and\s+){_ITEM.pattern})+"
)
_RESPECTIVELY = re.compile(r"\s*\)?\s*,?\s*(?i:respectively)\b")
_LIST_LEAD = re.compile(r"(?i:\b(?:masses|abundances))\s*(?:(?i:of|are|:|=)\s*)?$")
# A sentence ends at a full stop, question mark or semicolon that no digit follows.
_SENTENCE_END = re.compile(r"[.?!;](?!\d)")

# A table's header line, which names its columns in order.
_COLUMN = re.compile(
    r"(?i:\b(?P<number>mass\s+numbers?)|\b(?P<mass>(?:atomic\s+|isotopic\s+)?mass(?:es)?)"
    r"|\b(?P<abundance>(?:relative\s+|natural\s+|percent(?:age)?\s+)?abundances?))\b"
)
# A stated mass this far from its mass number belongs to something else (a sample).
_MASS_NUMBER_GAP = 1.0


def _isotopes(text: str) -> list[tuple[str, int, int, int]]:
    """Each isotope written in the text: (symbol, mass number, start, end)."""
    found: list[tuple[str, int, int, int]] = []
    for match in _ISOTOPE.finditer(text):
        token = match.group("symbol") or match.group("element")
        symbol = token if token in BY_SYMBOL else ELEMENT_NAMES.get(token.lower())
        number = int(match.group("before") or match.group("after"))
        if symbol is None or number < BY_SYMBOL[symbol].number:
            return []
        found.append((symbol, number, match.start(), match.end()))
    return found


def _one_abundance(segment: str) -> float | None:
    values = [float(match.group(1)) for match in _ABUNDANCE.finditer(segment)]
    return values[0] if len(values) == 1 else None


def _one_mass(segment: str) -> float | None:
    values = [float(match.group(1) or match.group(2)) for match in _STATED_MASS.finditer(segment)]
    return values[0] if len(values) == 1 else None


def _sentence_before(text: str, start: int) -> str:
    ends = [match.end() for match in _SENTENCE_END.finditer(text, 0, start)]
    return text[ends[-1] if ends else 0 : start]


def _lists(text: str, count: int) -> tuple[list[float] | None, list[float] | None, str]:
    """Masses and abundances given as lists in the isotopes' order, and the text without them.

    A list counts only when it names every isotope and says it is theirs: "respectively"
    follows it, or "masses" or "abundances" leads it. Percent signs make it the abundances;
    bare numbers or units, in a sentence about masses, the masses.
    """
    masses: list[float] | None = None
    abundances: list[float] | None = None
    blanked = text
    for match in _LIST.finditer(text):
        items = list(_ITEM.finditer(match.group()))
        lead = _sentence_before(text, match.start())
        if len(items) != count or not (
            _RESPECTIVELY.match(text, match.end()) or _LIST_LEAD.search(lead)
        ):
            continue
        values = [float(item.group(1)) for item in items]
        signs = {item.group(2) == "%" for item in items}
        if signs == {True} and abundances is None:
            abundances = values
        elif signs == {False} and masses is None and re.search(_MASS_WORD, lead):
            masses = values
        else:
            continue
        blanked = blanked[: match.start()] + " " * len(match.group()) + blanked[match.end() :]
    return masses, abundances, blanked


def _table(
    text: str, isotopes: list[tuple[str, int, int, int]]
) -> tuple[list[float], list[float]] | None:
    """Masses and abundances from rows under a header line naming the columns.

    "Isotope | Mass (u) | Abundance (%)" over "24Mg | 23.985 | 78.99": each row holds one
    number per named column. Abundances that add to 1 are fractions of the whole.
    """
    above = text[: text.rfind("\n", 0, isotopes[0][2]) + 1].splitlines()
    # A markdown table's |---|---| rule sits between the header and the rows.
    while above and not above[-1].strip(" \t|-:"):
        above.pop()
    if not above:
        return None
    header = above[-1]
    columns = [match.lastgroup for match in _COLUMN.finditer(header)]
    if "mass" not in columns or "abundance" not in columns:
        return None
    masses: list[float] = []
    abundances: list[float] = []
    for _symbol, _number, start, end in isotopes:
        # Each isotope opens its own row.
        if text[text.rfind("\n", 0, start) + 1 : start].strip(" \t|"):
            return None
        line_end = text.find("\n", end)
        row = text[end : len(text) if line_end < 0 else line_end]
        values = [float(match.group(1)) for match in _ITEM.finditer(row)]
        if len(values) != len(columns):
            return None
        masses.append(values[columns.index("mass")])
        abundances.append(values[columns.index("abundance")])
    if abs(sum(abundances) - 1) <= 0.001:
        abundances = [value * 100 for value in abundances]
    return masses, abundances


def extract_average_atomic_mass(text: str) -> ChemistryIntent | None:
    """Isotopes with their abundances: Σ mass × abundance / 100."""
    if not _AVERAGE_ASK.search(text):
        return None
    isotopes = _isotopes(text)
    if len(isotopes) < 2 or len({symbol for symbol, *_ in isotopes}) != 1:
        return None
    table = _table(text, isotopes)
    listed_masses: list[float] | None
    listed_abundances: list[float] | None
    if table is not None:
        listed_masses, listed_abundances = table
        blanked = " " * len(text)
    else:
        listed_masses, listed_abundances, blanked = _lists(text, len(isotopes))
    ends = [start for _, _, start, _ in isotopes[1:]] + [len(blanked)]
    abundances: dict[str, float] = {}
    masses: dict[str, float] = {}
    for index, ((symbol, number, _start, end), stop) in enumerate(zip(isotopes, ends, strict=True)):
        segment = blanked[end:stop]
        abundance = _one_abundance(segment)
        stated = _one_mass(segment)
        if listed_abundances is not None:
            if abundance is not None:
                return None  # given twice: which one holds is not ours to pick
            abundance = listed_abundances[index]
        if listed_masses is not None:
            if stated is not None:
                return None
            stated = listed_masses[index]
        if stated is not None and abs(stated - number) > _MASS_NUMBER_GAP:
            return None
        mass = stated if stated is not None else ISOTOPE_MASSES.get((symbol, number))
        label = f"{symbol}-{number}"
        if abundance is None or mass is None or label in abundances:
            return None
        abundances[label] = abundance
        masses[label] = mass
    if abs(sum(abundances.values()) - 100) > 0.1:
        return None
    return ChemistryIntent(
        kind="amounts",
        chemistry_op="average_atomic_mass",
        target=isotopes[0][0],
        species=abundances,
        params=masses,
    )
