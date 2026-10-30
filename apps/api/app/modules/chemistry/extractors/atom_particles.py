# ruff: noqa: RUF001, RUF002, RUF003 -- a charge is written with a minus sign or a dash.
"""An atom's particles read from what a question gives: A, Z, protons, neutrons, electrons.

"An atom 70X has 31 electrons. How many neutrons?" was answered 70 − 31 = 40, and
"magnesium, mass number 24, atomic number 12: protons, neutrons, electrons and the
arrangement" with the neutrons alone (2026-10-30, a Class 9 book). One reader takes every
fact a question states about one atom or ion, in any order and notation (``70X``,
``27Al``, ``Al-27``, ``Hg2+``, "atomic number 15", "18 neutrons", "magnesium"), and asks
the solver for every quantity it names that was not given.
"""

from __future__ import annotations

import re

from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.schemas import ChemistryIntent
from app.modules.chemistry.species_facts import ELEMENT_NAMES

_N = r"(\d{1,3})"
_LINK = r"\s*(?:of\s+(?:an?\s+|the\s+)?(?:[a-z]+\s+)?|is\s+|=|:|equal\s+to\s+|as\s+)?\s*"
_FACTS: dict[str, tuple[re.Pattern[str], ...]] = {
    "mass_number": (
        re.compile(rf"\bmass\s+number{_LINK}{_N}\b", re.IGNORECASE),
        re.compile(rf"\b{_N}\s+(?:is\s+(?:its|the)\s+|as\s+(?:its|the)\s+)?mass\s+number", re.I),
    ),
    "atomic_number": (
        re.compile(rf"\batomic\s+number{_LINK}{_N}\b", re.IGNORECASE),
        re.compile(rf"\b{_N}\s+(?:is\s+(?:its|the)\s+|as\s+(?:its|the)\s+)?atomic\s+number", re.I),
    ),
    "protons": (
        re.compile(rf"\b{_N}\s+protons?\b", re.IGNORECASE),
        re.compile(rf"\bprotons?\s*(?:=|:|is|are)\s*{_N}\b", re.IGNORECASE),
    ),
    "neutrons": (
        re.compile(rf"\b{_N}\s+neutrons?\b", re.IGNORECASE),
        re.compile(rf"\bneutrons?\s*(?:=|:|is|are)\s*{_N}\b", re.IGNORECASE),
    ),
    "electrons": (
        re.compile(rf"\b{_N}\s+(?!valence|outer|shared|unpaired|lone)electrons?\b", re.I),
        re.compile(rf"(?<!valence\s)\belectrons?\s*(?:=|:|is|are)\s*{_N}\b", re.IGNORECASE),
    ),
}
# "70X", "27Al", "^{27}Al", "Al-27", "201Hg2+", "80Br–": a nuclide or an ion written out.
_NUCLIDE = re.compile(
    r"(?<![\w^{])(?:\^\{?)?(?P<mass>\d{1,3})\}?(?P<symbol>[A-Z][a-z]?)"
    r"(?P<charge>\d?[+\-−–])?(?![a-z])"
    r"|\b(?P<symbol2>[A-Z][a-z]?|[a-z]{3,})-(?P<mass2>\d{1,3})\b"
)
_ION = re.compile(r"(?<![\w])(?P<symbol>[A-Z][a-z]?)(?P<charge>\d?[+\-−–])(?![\w])")
_CHARGE_WORDS = re.compile(r"\bcharge\s+(?:of\s+)?(?P<sign>[+\-−])\s?(?P<size>\d)\b", re.I)
_PARTICLE = re.compile(r"\b(?:protons?|neutrons?|electrons?|atomic\s+number|mass\s+number)\b", re.I)
# Each quantity a question can ask for, by the words that ask it.
_ASKED: dict[str, re.Pattern[str]] = {
    "protons": re.compile(r"\bprotons?\b", re.IGNORECASE),
    "neutrons": re.compile(r"\bneutrons?\b", re.IGNORECASE),
    "electrons": re.compile(r"\belectrons?\b(?!\s+(?:with|that|are\s+replaced))", re.I),
    "atomic_number": re.compile(r"\batomic\s+number\b", re.IGNORECASE),
    "mass_number": re.compile(r"\bmass\s+number\b", re.IGNORECASE),
    "configuration": re.compile(
        r"\b(?:electronic|electron)\s+(?:configuration|arrangement|distribution)"
        r"|\barrangement\s+of\s+(?:the\s+)?electrons\b",
        re.IGNORECASE,
    ),
    "valence": re.compile(r"\bvalence\s+electrons?\b", re.IGNORECASE),
    "valency": re.compile(r"\bvalency\b", re.IGNORECASE),
    "name": re.compile(
        r"\b(?:name|identify)\s+(?:the\s+)?(?:element|species|atom)|\bwhich\s+element\b"
        r"|\bname\s+of\s+the\s+element",
        re.IGNORECASE,
    ),
    "kind": re.compile(r"\bneutral\b.*\b(?:cation|anion)\b", re.IGNORECASE | re.DOTALL),
    "charge": re.compile(r"\b(?:its|the|what)\s+(?:\w+\s+)?charge\b", re.IGNORECASE),
}
# Not one atom: amounts, reactions, several species, or a hypothetical particle.
_DECLINE = re.compile(
    r"\b(?:moles?|mol|grams?|molecules?|compounds?|reaction|isotopes\s+of|hypothetical"
    r"|replaced|table|respectively|ratio|percentage|abundance|average)\b",
    re.IGNORECASE,
)
_ATOM = re.compile(r"\batom\b(?!ic)", re.IGNORECASE)
_SHELL_RULE_LAST = 20
# One number a one-line law already reads ("how many neutrons in carbon-14", "the charge
# of the ion"): that law answers it, in its own layout.
_ONE_LAWS = frozenset({"neutron_count", "ion_charge"})
_SIGN = {"+": 1, "-": -1, "−": -1, "–": -1}


def _one_law_reads(text: str) -> bool:
    from app.modules.chemistry.binding import bind_chemistry_intent

    bound = bind_chemistry_intent(text)
    return bound is not None and bound.chemistry_op in _ONE_LAWS


def _element(word: str) -> str | None:
    if word in BY_SYMBOL:
        return word
    return ELEMENT_NAMES.get(word.lower())


def _charge(text: str) -> int | None:
    if not text:
        return None
    size = int(text[:-1]) if text[:-1] else 1
    return size * _SIGN[text[-1]]


def _named_elements(text: str) -> set[str]:
    words = re.findall(r"[A-Za-z]+", text)
    return {ELEMENT_NAMES[word.lower()] for word in words if word.lower() in ELEMENT_NAMES}


def extract_atom_particles(text: str) -> ChemistryIntent | None:
    """One atom or ion: the facts given, and the quantities asked that were not."""
    if _PARTICLE.search(text) is None or _DECLINE.search(text):
        return None
    params: dict[str, float] = {}
    for name, patterns in _FACTS.items():
        values = {int(m.group(1)) for pattern in patterns for m in pattern.finditer(text)}
        if len(values) > 1:
            return None
        if values:
            params[name] = float(values.pop())
    symbol: str | None = None
    nuclides = list(_NUCLIDE.finditer(text))
    if len(nuclides) > 1:
        return None
    if nuclides:
        found = nuclides[0]
        written = found.group("symbol") or found.group("symbol2") or ""
        mass = int(found.group("mass") or found.group("mass2"))
        if params.get("mass_number", mass) != mass:
            return None
        params["mass_number"] = float(mass)
        symbol = _element(written)
        if symbol is None and not re.fullmatch(r"[A-Z]", written):
            return None
        # A nucleus holds at least its protons and at most about three times as many
        # nucleons: "150 V" is a voltage, never vanadium-150.
        if (
            symbol is not None
            and not BY_SYMBOL[symbol].number <= mass <= 3 * BY_SYMBOL[symbol].number
        ):
            return None
        charge = _charge(found.group("charge") or "")
        if charge is not None:
            params["charge"] = float(charge)
    ions = [match for match in _ION.finditer(text) if _element(match.group("symbol"))]
    if not nuclides and len(ions) == 1:
        symbol = ions[0].group("symbol")
        params["charge"] = float(_charge(ions[0].group("charge")) or 0)
    worded = _CHARGE_WORDS.search(text)
    if worded and "charge" not in params:
        params["charge"] = float(_SIGN[worded.group("sign")] * int(worded.group("size")))
    named = _named_elements(text) - ({symbol} if symbol else set())
    if symbol is None and len(named) == 1:
        symbol = named.pop()
    elif named:
        return None
    asked = [
        name for name, pattern in _ASKED.items() if pattern.search(text) and name not in params
    ]
    # Two facts, or an atomic number stated alone for what it decides by itself (its
    # arrangement, valency, protons): "the valency of an element with atomic number 16".
    # An element named alone is the configuration reader's, past calcium too.
    facts = len(params) + (symbol is not None)
    by_number = "atomic_number" in params or "protons" in params
    alone = {"configuration", "valence", "valency", "protons", "electrons", "name", "atomic_number"}
    if not asked or (facts < 2 and not (by_number and set(asked) <= alone)):
        return None
    # The shell rule stops at calcium: Fe3+'s configuration is the aufbau reader's to decline.
    z = BY_SYMBOL[symbol].number if symbol else params.get("atomic_number", params.get("protons"))
    if {"configuration", "valence", "valency"} & set(asked) and (z or 0) > _SHELL_RULE_LAST:
        return None
    if len(asked) == 1 and _one_law_reads(text):
        return None
    return ChemistryIntent(
        kind="structure",
        chemistry_op="atom_particles",
        params=params,
        formula=symbol,
        # "an atom" is neutral; an ion or a "species" says its charge or has none to assume.
        target=",".join(asked) + ("|atom" if _ATOM.search(text) else ""),
    )
