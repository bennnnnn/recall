"""Read a chemistry question in its own words into one law, with the shared binder.

The extractors in ``extractors/`` read the phrasings they were written for ("Strong acid:
0.01 M HCl"). A student writes "What is the pH of 0.01 M HCl?". The binder reads that
second kind after every extractor has declined:

- the text is prepared first: a symbol whose case is its meaning is spelled out ("pH" is
  ``p_h``, "Ka" is ``k_a``), and each named substance becomes its role ("HCl" is
  ``acid_strong``, "sodium acetate" is ``salt_conjugate``), so its digits are never read as
  numbers and the words around a value can say whose it is;
- a law (``laws.LAWS``) is tried only when the question names the substance it is about:
  a strong-acid pH needs exactly one strong acid;
- the shared engine (``services.law_binding.fit``) fills the law's inputs from the stated
  values by dimension and by the words around them, and settings fill the rest (the van 't
  Hoff factor of a named solute, the molar mass of the metal deposited);
- each input is converted to the unit its solver reads, and the solver is the same one a
  template intent reaches.

Anything short of one law with one way to fill it declines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache, partial

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.formula_laws import FORMULA_LAWS
from app.modules.chemistry.given_units import CHEMISTRY_UNITS
from app.modules.chemistry.laws import LAWS, ChemistryLaw
from app.modules.chemistry.solvers.constants import STANDARD_REDUCTION
from app.modules.chemistry.species_facts import (
    CONJUGATE_SALTS,
    ELEMENT_NAMES,
    NAMED_COMPOUNDS,
    STRONG_ACIDS,
    STRONG_BASES,
    VAN_T_HOFF,
    WEAK_ACIDS,
    WEAK_BASES,
    ion_charge,
    is_formula,
)
from app.modules.chemistry.stoichiometry import molar_mass
from app.services.law_binding.ask import ask_clause
from app.services.law_binding.fit import Fit, Question, Subject, fit, read_givens
from app.services.law_binding.spec import VariableSpec
from app.services.law_binding.words import ask_strength, word_pattern

_VERBS = re.compile(
    r"\b(?:find|calculate|compute|determine|work\s+out|estimate|evaluate|what|convert|"
    r"how\s+(?:long|far|fast|high|deep|much|many))\b",
    re.IGNORECASE,
)
# A school question states a handful of values; a paste full of numbers is not one law's.
_MAX_GIVENS = 12
# A second request ("... and explain why") is not a question the verified answer finishes.
_SECOND_REQUEST = re.compile(
    r"\b(?:and|also|then)\s+(?:also\s+)?"
    r"(?:tell|explain|show|write|give|draw|plot|describe)\b",
    re.IGNORECASE,
)
_STANDARD_TEMPERATURE = 298.15

# Symbols whose case is their meaning, spelled out so lowercase word windows keep it.
_SYMBOLS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), spelled)
    for pattern, spelled in (
        (r"\[A\](?:0|₀)", " a_initial "),
        (r"\[A\]", " a_conc "),
        (r"(?<![A-Za-z])E(?:°|0|º)(?:\s*cell)?(?![A-Za-z0-9])", " e_standard "),
        (r"(?<![A-Za-z])E(?:a|ₐ)(?![A-Za-z0-9])", " e_a "),
        (r"(?<![A-Za-z0-9])E(?![A-Za-z0-9°º₀_])", " e_cell "),
        (r"Δ\s*G|\bdelta\s*G\b", " delta_g "),
        (r"Δ\s*H|\bdelta\s*H\b", " delta_h "),
        (r"Δ\s*S|\bdelta\s*S\b", " delta_s "),
        (r"(?<![A-Za-z])pOH(?![A-Za-z])", " p_oh "),
        (r"(?<![A-Za-z])pKa(?![A-Za-z0-9])", " p_ka "),
        (r"(?<![A-Za-z])pKb(?![A-Za-z0-9])", " p_kb "),
        (r"(?<![A-Za-z])pH(?![A-Za-z])", " p_h "),
        (r"(?<![A-Za-z])Ksp(?![A-Za-z])", " k_sp "),
        (r"(?<![A-Za-z])Ka(?![A-Za-z0-9])", " k_a "),
        (r"(?<![A-Za-z])Kb(?![A-Za-z0-9])", " k_b "),
        (r"(?<![A-Za-z])Kf(?![A-Za-z])", " k_f "),
        (r"(?<![A-Za-z])R(?:f|F)(?![A-Za-z])", " r_f "),
    )
)
_FORMULA_TOKEN = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9()]*)(?![A-Za-z0-9(])")
# Subscript digits a typeset answer copies back (K₂, T₁) beside the ASCII labels.
_SUBSCRIPT_DIGITS = "\u2081\u2082"
_SUBSCRIPT_TO_ASCII = str.maketrans(_SUBSCRIPT_DIGITS, "12")
_INDEXED_LABEL = re.compile(
    rf"(?<![A-Za-z])([KT])([12{_SUBSCRIPT_DIGITS}])(?![A-Za-z0-9{_SUBSCRIPT_DIGITS}])"
)
_ION = re.compile(r"(?<![A-Za-z0-9])([A-Z][a-z]?)(\d?)\+")
_ELEMENT_SYMBOL = re.compile(r"(?<![A-Za-z0-9])([A-Z][a-z]?)(?![A-Za-z0-9])")
# Metals a deposition can plate, from the galvanic table (not H, and not K: kelvin).
_METALS = frozenset(STANDARD_REDUCTION) - {"H", "K"}


def _spell_indexed_label(match: re.Match[str]) -> str:
    """Spell K1/K2 and T1/T2, including subscript digits, before formula roles."""
    digit = match.group(2).translate(_SUBSCRIPT_TO_ASCII)
    return f" {match.group(1).lower()}{digit} "


def role(formula: str) -> str:
    """What a named substance is in water, as the word the laws' windows read."""
    if formula in STRONG_ACIDS:
        return "acid_strong"
    if formula in STRONG_BASES:
        return "base_strong"
    if formula in WEAK_ACIDS:
        return "acid_weak"
    if formula in WEAK_BASES:
        return "base_weak"
    if formula in CONJUGATE_SALTS:
        return "salt_conjugate"
    return "water" if formula == "H2O" else "compound"


@dataclass(frozen=True, slots=True)
class Prepared:
    """A question with its substances replaced by their roles, and what they were."""

    text: str
    species: tuple[str, ...]
    original: str


def prepare(text: str) -> Prepared:
    """Spell out case-sensitive symbols and replace each named substance by its role."""
    species: list[str] = []

    def substance(formula: str) -> str:
        if formula not in species:
            species.append(formula)
        return f" {role(formula)} "

    names = "|".join(re.escape(name) for name in sorted(NAMED_COMPOUNDS, key=len, reverse=True))
    prepared = re.sub(
        rf"\b({names})\b",
        lambda match: substance(NAMED_COMPOUNDS[match.group(1).lower()]),
        text,
        flags=re.IGNORECASE,
    )
    # K1 and K2 are the two equilibrium constants in a van 't Hoff question. K2 is also
    # a formula (K₂), so spell them out before formulas are replaced by their roles.
    # A typeset answer copies the same labels back with subscript digits (K₁, T₁).
    prepared = _INDEXED_LABEL.sub(_spell_indexed_label, prepared)
    prepared = _ION.sub(lambda match: f" ion_{match.group(1).lower()} ", prepared)
    prepared = _FORMULA_TOKEN.sub(
        lambda match: substance(match.group(1)) if is_formula(match.group(1)) else match.group(0),
        prepared,
    )
    for pattern, spelled in _SYMBOLS:
        prepared = pattern.sub(spelled, prepared)
    return Prepared(re.sub(r"[ \t]+", " ", prepared), tuple(species), text)


def _formula_for(law: ChemistryLaw, species: tuple[str, ...]) -> str | bool | None:
    """The formula the law is about; None when it needs none; False when none fits."""
    if law.species is None:
        return None
    if law.species == "compound":
        return species[0] if len(species) == 1 else False
    if law.species == "solute":
        solutes = [formula for formula in species if formula != "H2O"]
        return solutes[0] if len(solutes) == 1 else False
    matching = [formula for formula in species if role(formula) == law.species]
    return matching[0] if len(matching) == 1 else False


def _metal(original: str) -> str | None:
    """The one metal a deposition question names, by symbol ("Cu") or name ("copper")."""
    found = {match.group(1) for match in _ELEMENT_SYMBOL.finditer(original)}
    found |= {match.group(1) for match in _ION.finditer(original)}
    found |= {
        ELEMENT_NAMES[word]
        for word in re.findall(r"[a-z]+", original.lower())
        if word in ELEMENT_NAMES
    }
    found &= _METALS
    return next(iter(found)) if len(found) == 1 else None


def _fallback(prepared: Prepared, variable: VariableSpec, _text: str, _lower: str) -> float | None:
    """A setting an unstated input takes from the substances the question names."""
    if variable.fallback == "van_t_hoff":
        solutes = [formula for formula in prepared.species if formula != "H2O"]
        factor = VAN_T_HOFF.get(solutes[0]) if len(solutes) == 1 else None
        return None if factor is None else float(factor)
    if variable.fallback == "standard_temperature":
        return _STANDARD_TEMPERATURE
    if variable.fallback == "species_molar_mass":
        solutes = [formula for formula in prepared.species if formula != "H2O"]
        named = solutes if len(solutes) == 1 else list(prepared.species)
        return molar_mass(named[0]) if len(named) == 1 else None
    if variable.fallback not in {"deposited_molar_mass", "ion_charge"}:
        return None
    metal = _metal(prepared.original)
    if metal is None:
        return None
    if variable.fallback == "deposited_molar_mass":
        return BY_SYMBOL[metal].mass
    # "Cu2+" states the ion; otherwise it is the galvanic table's school ion (Cu²⁺).
    charge = ion_charge(prepared.original, metal)
    return float(charge if charge is not None else STANDARD_REDUCTION[metal][1])


def _declared(variable: VariableSpec) -> str:
    return variable.dimension or ""


def _converted(law: ChemistryLaw, filled: Fit) -> tuple[dict[str, float], dict[str, str]] | None:
    """The filled inputs in the units the law's solver reads, and the units it is told."""
    from app.services.units import get_unit_registry

    registry = get_unit_registry()
    params: dict[str, float] = {}
    units: dict[str, str] = {}
    for variable in law.spec.variables:
        if variable.name not in filled.params:
            continue
        value, written = filled.params[variable.name], filled.units[variable.name]
        if variable.dimensionless or variable.name in law.keep_units:
            params[variable.name] = value
            if variable.name in law.keep_units:
                units[variable.name] = written
            continue
        if written == variable.dimension:
            params[variable.name] = value
            continue
        expression = CHEMISTRY_UNITS.expression(written)
        if expression is None or variable.dimension is None:
            return None
        try:
            quantity = registry.Quantity(value, expression).to(variable.dimension)
        except Exception:
            return None
        params[variable.name] = float(quantity.magnitude)
        if law.op in FORMULA_LAWS:
            # The formula solver echoes the given as typed before the converted value.
            units[variable.name] = written
    units.update(dict(law.labels))
    return params, units


def bind_chemistry_intent(text: str) -> ChemistryIntent | None:
    """The one chemistry law this question states and asks for, or None.

    The gate and extraction both ask about the same line, so it is read once and each
    caller gets its own copy.
    """
    intent = _bind(text)
    return None if intent is None else intent.model_copy(deep=True)


@lru_cache(maxsize=128)
def _bind(text: str) -> ChemistryIntent | None:
    if _SECOND_REQUEST.search(text):
        return None
    prepared = prepare(text)
    clause = ask_clause(prepared.text, _VERBS)
    if clause is None:
        return None
    lower = prepared.text.lower()
    asked_clause = clause.lower()
    named = [
        (law, formula, strength)
        for law in LAWS
        if (binding := law.spec.binding) is not None
        and (formula := _formula_for(law, prepared.species)) is not False
        and (not binding.cues or any(word_pattern(cue).search(lower) for cue in binding.cues))
        and not any(word_pattern(word).search(lower) for word in binding.excludes)
        and (strength := ask_strength(clause, binding.asks, binding.result, CHEMISTRY_UNITS))
    ]
    if not named:
        return None
    givens = read_givens(prepared.text, CHEMISTRY_UNITS)
    if len(givens) > _MAX_GIVENS:
        return None
    question = Question(
        text=prepared.text,
        lower=lower,
        givens=givens,
        asked=frozenset(),
        asked_in=None,
        asked_from=lower.rfind(asked_clause),
    )
    subject = Subject(
        units=CHEMISTRY_UNITS, fallback=partial(_fallback, prepared), unit_of=_declared
    )
    fits = [
        (law, formula, filled)
        for law, formula, strength in named
        if (filled := fit(law.spec, strength, question, subject)) is not None
    ]
    if not fits:
        return None
    strongest = max(filled.strength for _, _, filled in fits)
    top = [entry for entry in fits if entry[2].strength == strongest]
    if len(top) != 1:
        return None
    law, formula, filled = top[0]
    converted = _converted(law, filled)
    if converted is None:
        return None
    params, units = converted
    try:
        return ChemistryIntent(
            kind=law.kind,  # type: ignore[arg-type]
            chemistry_op=law.op,  # type: ignore[arg-type]
            params=params,
            units=units,
            formula=formula if isinstance(formula, str) else None,
        )
    except ValueError:
        return None
