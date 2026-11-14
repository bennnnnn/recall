"""The substances a question names in its own words, as the formulas a reaction is built from.

A student types "4g of h2", "burn hydrogen", "magnesium oxide" or "CO2" (live, 2026-10-25:
"how much water do i get if i burn like 4g of h2"). Each names one formula:

- a compound by its common name ("water", "propane": ``NAMED_COMPOUNDS``), or a salt the ion
  table names ("magnesium oxide" is MgO);
- an element named in words, as it reacts: hydrogen is H2, magnesium Mg. Before "bond",
  "atoms" or "ion" the word names no substance, and before a compound word the tables do not
  hold ("hydrogen peroxide", "iron oxide") the substance is unknown, so nothing is read;
- a formula as written: a compound or a molecule ("CO2", "O2"). A bare symbol ("C", "Mg")
  counts only as what a stated amount is of ("12 g of C"): "C" is also Celsius, "I" a pronoun;
- a formula typed in lowercase, with a digit, when exactly one reading is a school substance
  (``lowercase_formulas``): "co2" is CO2 (cobalt is never written Co2), "nh3" NH3, "fe2o3"
  Fe2O3. "caco3" could be CaCO3 or CaCo3 and is not read; "co", "no" and "hf" have no digit and
  stay words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from app.modules.chemistry.elements import BY_SYMBOL, DIATOMIC_ELEMENTS
from app.modules.chemistry.lowercase_formulas import MAX_LOWERCASE, lowercase_formula
from app.modules.chemistry.nomenclature import salt_from_name
from app.modules.chemistry.species_facts import ELEMENT_NAMES, NAMED_COMPOUNDS, is_formula
from app.services.number_text import TEXT_NUMBER

# Tokens are bounded, so a run such as "a1(a1(a1(…" is read in linear time: it was cubic, 8.7 s
# on 4,000 characters, and the gate reads every turn.
_FORMULA_TOKEN = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9()]{0,39})(?![A-Za-z0-9(_])")
_LOWERCASE_TOKEN = re.compile(
    rf"(?<![A-Za-z0-9])([a-z][a-z0-9()]{{0,{MAX_LOWERCASE - 1}}})(?![A-Za-z0-9(])"
)
# "OK so…" opens a sentence; no school formula is written OK.
_NOT_FORMULAS = frozenset({"OK"})
# "atoms of oxygen" counts O atoms, not O2 molecules: after it an element is no molecule.
_ATOMS_OF = re.compile(r"\batoms?\s+of\s+(?:the\s+)?\Z", re.IGNORECASE)
_AMOUNT_BEFORE = re.compile(rf"{TEXT_NUMBER}\s*(?:g|grams?|mol|moles?)\s+(?:of\s+)?\Z")
# How far back an amount phrase can start ("1.20e+24 grams of "), so the look stays short.
_AMOUNT_REACH = 48
# After an element's name, a word that makes it something other than the substance.
_NOT_THE_SUBSTANCE = frozenset(
    {"bond", "bonds", "bonding", "atom", "atoms", "atomic", "ion", "ions", "isotope", "isotopes"}
)
_COMPOUND_WORD = re.compile(r"[a-z]+(?:ide|ate|ite)|acid", re.IGNORECASE)
_ROMAN = r"(?:\s*\(\s*[IVXivx]+\s*\))?"


@dataclass(frozen=True, slots=True)
class Mention:
    """Where the text names a substance, and the formula it names."""

    start: int
    end: int
    formula: str


@lru_cache(maxsize=1)
def _name_pattern() -> re.Pattern[str]:
    """Compound names and element names, longest first, with the word after each."""
    names = sorted({*NAMED_COMPOUNDS, *ELEMENT_NAMES}, key=len, reverse=True)
    return re.compile(
        r"\b(?P<name>" + "|".join(re.escape(name) for name in names) + rf")\b(?P<roman>{_ROMAN})"
        r"(?=\s+(?P<next>[A-Za-z]+))?",
        re.IGNORECASE,
    )


def _named(match: re.Match[str]) -> Mention | Literal["none", "unknown"]:
    """The substance a name names: "none" when the next word says it names none, "unknown"
    when it heads a compound name no table holds."""
    name = match.group("name").lower()
    compound = NAMED_COMPOUNDS.get(name)
    if compound is not None:
        return Mention(match.start("name"), match.end("name"), compound)
    following = (match.group("next") or "").lower()
    if following in _NOT_THE_SUBSTANCE:
        return "none"
    if _COMPOUND_WORD.fullmatch(following):
        salt = salt_from_name(f"{name}{match.group('roman')} {following}")
        return (
            "unknown" if salt is None else Mention(match.start(), match.end("next"), salt.formula)
        )
    symbol = ELEMENT_NAMES[name]
    if symbol not in DIATOMIC_ELEMENTS:
        return Mention(match.start("name"), match.end("name"), symbol)
    before = max(0, match.start() - _AMOUNT_REACH)
    if _ATOMS_OF.search(match.string, before, match.start()):
        return "unknown"
    return Mention(match.start("name"), match.end("name"), f"{symbol}2")


def _written(text: str) -> list[Mention]:
    """Formulas as written, and lowercase formulas a single reading names."""
    found: list[Mention] = []
    for match in _FORMULA_TOKEN.finditer(text):
        token = match.group(1)
        before = max(0, match.start() - _AMOUNT_REACH)
        amount_of = _AMOUNT_BEFORE.search(text, before, match.start()) is not None
        if token in _NOT_FORMULAS:
            continue
        if is_formula(token) or (amount_of and token in BY_SYMBOL):
            found.append(Mention(match.start(), match.end(), token))
    for match in _LOWERCASE_TOKEN.finditer(text):
        if not any(char.isdigit() for char in match.group(1)):
            continue
        formula = lowercase_formula(match.group(1))
        if formula is not None:
            found.append(Mention(match.start(), match.end(), formula))
    return found


def substance_mentions(text: str) -> tuple[Mention, ...] | None:
    """Every substance the text names, in order; None when it names one no table writes."""
    found = _written(text)
    for match in _name_pattern().finditer(text):
        named = _named(match)
        if named == "unknown":
            return None
        if isinstance(named, Mention):
            found.append(named)
    kept: list[Mention] = []
    for mention in sorted(found, key=lambda mention: (mention.start, -mention.end)):
        if not kept or mention.start >= kept[-1].end:
            kept.append(mention)
    return tuple(kept)


def with_formulas(text: str, mentions: tuple[Mention, ...]) -> str:
    """The text with each substance written as its formula: "4g of h2" is "4g of H2"."""
    parts: list[str] = []
    at = 0
    for mention in mentions:
        parts.extend((text[at : mention.start], mention.formula))
        at = mention.end
    parts.append(text[at:])
    return "".join(parts)
