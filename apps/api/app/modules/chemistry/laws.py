"""The chemistry laws a question can be read into in its own words.

Each law is a ``FormulaSpec`` for the shared binder (``services.law_binding``) whose
variables are its solver's parameters, in the unit that solver reads them in: the binder
converts a stated 500 mL to the 0.5 L a molarity solver expects. The solver stays the one
in ``solvers/``; a law here only says how a question names its inputs and its ask.

Words are matched in the binder's prepared text (``binding.prepare``): case-sensitive
symbols are spelled out ("pH" is ``p_h``, "Ka" is ``k_a``, "E°" is ``e_standard``), and a
named substance is its role (``acid_strong``, ``base_weak``, ``salt_conjugate``).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.law_binding.spec import Binding, FormulaSpec, VariableSpec, var

_MOLAR = "mole / liter"
_MOLAL = "mole / kilogram"
_PER_SECOND = "1 / second"
_PH_ASKS = ("p_h",)


@dataclass(frozen=True, slots=True)
class ChemistryLaw:
    """One law the binder can fill, and the solver operation that answers it."""

    op: str
    kind: str
    spec: FormulaSpec
    # The role of the substance the law is about ("acid_strong"); its formula goes on the intent.
    species: str | None = None
    # Inputs passed in the unit the question wrote, with that unit on the intent.
    keep_units: tuple[str, ...] = ()
    # Units the solver reads off the intent, as the converted inputs are in.
    labels: tuple[tuple[str, str], ...] = ()


def _law(
    op: str,
    kind: str,
    asks: tuple[str, ...],
    result: str,
    variables: tuple[VariableSpec, ...],
    *,
    name: str | None = None,
    inputs: tuple[frozenset[str], ...] | None = None,
    cues: tuple[str, ...] = (),
    excludes: tuple[str, ...] = (),
    interchangeable: tuple[str, ...] = (),
    species: str | None = None,
    keep_units: tuple[str, ...] = (),
    labels: tuple[tuple[str, str], ...] = (),
    nonnegative: bool = True,
) -> ChemistryLaw:
    names = frozenset(variable.name for variable in variables)
    binding = Binding(
        asks=asks,
        result=(result,),
        inputs=inputs or (names,),
        cues=cues,
        excludes=excludes,
        interchangeable=interchangeable,
        nonnegative=nonnegative,
    )
    spec = FormulaSpec(
        id=name or op,
        kind=kind,
        law_name=op,
        result_symbol="",
        variables=variables,
        binding=binding,
    )
    return ChemistryLaw(op, kind, spec, species, keep_units, labels)


def _concentration() -> VariableSpec:
    return var("concentration", "C", _MOLAR)


ACID_BASE: tuple[ChemistryLaw, ...] = (
    _law(
        "strong_acid_ph",
        "acid_base",
        _PH_ASKS,
        "dimensionless",
        (_concentration(),),
        species="acid_strong",
    ),
    _law(
        "strong_base_ph",
        "acid_base",
        _PH_ASKS,
        "dimensionless",
        (_concentration(),),
        species="base_strong",
    ),
    _law(
        "weak_acid_ph",
        "acid_base",
        _PH_ASKS,
        "dimensionless",
        (_concentration(), var("ka", "Ka", dimensionless=True, words=("k_a",), needs_words=True)),
        species="acid_weak",
    ),
    _law(
        "weak_base_ph",
        "acid_base",
        _PH_ASKS,
        "dimensionless",
        (_concentration(), var("kb", "Kb", dimensionless=True, words=("k_b",), needs_words=True)),
        species="base_weak",
    ),
    _law(
        "ph_from_poh",
        "acid_base",
        _PH_ASKS,
        "dimensionless",
        (var("poh", "pOH", dimensionless=True, words=("p_oh",), needs_words=True),),
        nonnegative=False,
    ),
    _law(
        "buffer_ph",
        "acid_base",
        _PH_ASKS,
        "dimensionless",
        (
            var("pka", "pKa", dimensionless=True, words=("p_ka",), needs_words=True),
            var("acid", "[HA]", _MOLAR, words=("acid",), needs_words=True),
            var("base", "[A-]", _MOLAR, words=("base", "salt"), needs_words=True),
        ),
        cues=("buffer",),
        nonnegative=False,
    ),
)

SOLUTIONS: tuple[ChemistryLaw, ...] = (
    _law(
        "dilution",
        "solutions",
        ("new concentration", "final concentration", "concentration", "molarity"),
        _MOLAR,
        (
            var("m1", "M1", _MOLAR),
            var("v1", "V1", "liter"),
            var("v2", "V2", "liter", words=("diluted to", "dilute it to", "final volume", "total")),
        ),
        cues=("dilut",),
        interchangeable=("v1", "v2"),
        keep_units=("v1", "v2"),
    ),
    _law(
        "freezing_depression",
        "solutions",
        ("freezing point depression", "freezing point", "depression"),
        "kelvin",
        (
            var(
                "i",
                "i",
                dimensionless=True,
                words=("i =", "van 't hoff", "van't hoff"),
                needs_words=True,
                fallback="van_t_hoff",
            ),
            var("kf", "Kf", "kelvin * kilogram / mole"),
            var("molality", "m", _MOLAL),
        ),
    ),
    _law(
        "boiling_elevation",
        "solutions",
        ("boiling point elevation", "boiling point", "elevation"),
        "kelvin",
        (
            var(
                "i",
                "i",
                dimensionless=True,
                words=("i =", "van 't hoff", "van't hoff"),
                needs_words=True,
                fallback="van_t_hoff",
            ),
            var("kb", "Kb", "kelvin * kilogram / mole"),
            var("molality", "m", _MOLAL),
        ),
    ),
    _law(
        "osmotic_pressure",
        "solutions",
        ("osmotic pressure",),
        "atmosphere",
        (
            var(
                "i",
                "i",
                dimensionless=True,
                words=("i =", "van 't hoff", "van't hoff"),
                needs_words=True,
                fallback="van_t_hoff",
            ),
            var("molarity", "M", _MOLAR),
            var("temperature", "T", "kelvin"),
        ),
    ),
)

AMOUNTS: tuple[ChemistryLaw, ...] = (
    _law(
        "mass_to_moles",
        "amounts",
        ("how many moles", "moles", "amount"),
        "mole",
        (var("mass", "m", "gram"),),
        species="compound",
        labels=(("mass", "g"),),
    ),
    _law(
        "moles_to_mass",
        "amounts",
        ("how many grams", "grams", "mass"),
        "gram",
        (var("moles", "n", "mole"),),
        species="compound",
        labels=(("moles", "mol"),),
    ),
    _law(
        "molecular_formula",
        "amounts",
        ("molecular formula",),
        "dimensionless",
        (var("molar_mass", "M", "gram / mole"),),
        species="compound",
    ),
    _law(
        "percent_yield",
        "amounts",
        ("percent yield", "percentage yield", "% yield"),
        "percent",
        (
            var("actual", "actual", "gram", words=("actual", "obtained", "isolated", "collected")),
            var("theoretical", "theoretical", "gram", words=("theoretical", "expected")),
        ),
    ),
)


def _integrated(op: str, order: str, rate_unit: str) -> ChemistryLaw:
    """[A] after a time, for one reaction order: k and t in seconds."""
    return _law(
        op,
        "kinetics",
        ("a_conc", "concentration", "how much"),
        _MOLAR,
        (
            var("initial", "[A]0", _MOLAR, words=("a_initial", "initial", "starting")),
            var("rate_constant", "k", rate_unit),
            var("time", "t", "second"),
        ),
        cues=(f"{order}-order", f"{order} order"),
        labels=(("time", "s"),),
    )


KINETICS: tuple[ChemistryLaw, ...] = (
    _integrated("first_order_concentration", "first", _PER_SECOND),
    _integrated("zero_order", "zero", "mole / liter / second"),
    _integrated("second_order", "second", "liter / mole / second"),
    _law(
        "arrhenius_two_point",
        "kinetics",
        ("activation energy", "e_a"),
        "kilojoule / mole",
        (
            var("k1", "k1", _PER_SECOND),
            var("t1", "T1", "kelvin"),
            var("k2", "k2", _PER_SECOND),
            var("t2", "T2", "kelvin"),
        ),
        interchangeable=("k1", "k2", "t1", "t2"),
    ),
)

ELECTROCHEMISTRY: tuple[ChemistryLaw, ...] = (
    _law(
        "nernst",
        "electrochemistry",
        ("e_cell", "cell potential", "potential"),
        "volt",
        (
            var("standard_potential", "E°", "volt", words=("e_standard", "standard")),
            var("electrons", "n", dimensionless=True, words=("n =", "electrons"), needs_words=True),
            var(
                "quotient",
                "Q",
                dimensionless=True,
                words=("q =", "reaction quotient", "quotient"),
                needs_words=True,
            ),
            var("temperature", "T", "kelvin", fallback="standard_temperature"),
        ),
        nonnegative=False,
    ),
    _law(
        "electrolysis_mass",
        "electrochemistry",
        ("how many grams", "grams", "mass"),
        "gram",
        (
            var("molar_mass", "M", "gram / mole", fallback="deposited_molar_mass"),
            var("current", "I", "ampere"),
            var("time", "t", "second"),
            var(
                "electrons",
                "n",
                dimensionless=True,
                words=("n =", "electrons"),
                needs_words=True,
                fallback="ion_charge",
            ),
        ),
        cues=("deposit", "electrolysis", "plated", "plating"),
    ),
)

THERMOCHEMISTRY: tuple[ChemistryLaw, ...] = (
    _law(
        "gibbs",
        "thermochemistry",
        ("delta_g", "gibbs", "free energy"),
        "kilojoule / mole",
        (
            var("delta_h", "ΔH", "kilojoule / mole"),
            var("delta_s", "ΔS", "kilojoule / mole / kelvin"),
            var("temperature", "T", "kelvin"),
        ),
        nonnegative=False,
    ),
)


def _beer_lambert(unknown: str, asks: tuple[str, ...], result: str) -> ChemistryLaw:
    variables = (
        var("absorbance", "A", dimensionless=True, words=("absorbance",), needs_words=True),
        var("epsilon", "ε", "liter / mole / centimeter"),
        var("path", "b", "centimeter"),
        var("concentration", "c", _MOLAR),
    )
    return _law(
        "beer_lambert",
        "spectroscopy",
        asks,
        result,
        tuple(variable for variable in variables if variable.name != unknown),
        name=f"beer_lambert_{unknown}",
    )


ANALYSIS: tuple[ChemistryLaw, ...] = (
    _beer_lambert("concentration", ("concentration", "molarity"), _MOLAR),
    _beer_lambert("absorbance", ("absorbance",), "dimensionless"),
    _beer_lambert("path", ("path length",), "centimeter"),
    _beer_lambert(
        "epsilon", ("molar absorptivity", "absorptivity", "ε"), "liter / mole / centimeter"
    ),
    _law(
        "percent_error",
        "analytical",
        ("percent error", "percentage error", "% error"),
        "percent",
        (
            var(
                "experimental",
                "experimental",
                dimensionless=True,
                words=("measured", "experimental", "observed", "obtained"),
                needs_words=True,
            ),
            var(
                "accepted",
                "accepted",
                dimensionless=True,
                words=("accepted", "true", "actual", "known", "literature"),
                needs_words=True,
            ),
        ),
    ),
    _law(
        "chromatography_rf",
        "analytical",
        ("r_f", "retention factor"),
        "dimensionless",
        (
            var("spot", "spot", "centimeter", words=("spot", "compound", "sample", "dye")),
            var("front", "front", "centimeter", words=("front", "solvent")),
        ),
    ),
)


def _molar_mass() -> VariableSpec:
    """The molar mass of the substance the question names, unless it states one."""
    return var("molar_mass", "M", "gram / mole", fallback="species_molar_mass")


_SOLUTE_WORDS = ("compound", "solute", "salt", "sugar")
_SOLVENT_WORDS = ("water", "solvent")
_GRAMS_ASKS = ("how many grams", "grams", "mass")

# Laws that are one line of arithmetic (formula_laws), read from a question in its words.
FORMULA_LAW_BINDINGS: tuple[ChemistryLaw, ...] = (
    _law(
        "solution_mass",
        "solutions",
        _GRAMS_ASKS,
        "gram",
        (var("concentration", "c", _MOLAR), var("volume_l", "V", "liter"), _molar_mass()),
        cues=("solution",),
        species="compound",
    ),
    _law(
        "molality_from_mass",
        "solutions",
        ("molality",),
        _MOLAL,
        (
            var("solute_mass", "m", "gram", words=_SOLUTE_WORDS),
            _molar_mass(),
            var("solvent_kg", "m", "kilogram", words=_SOLVENT_WORDS),
        ),
        species="solute",
    ),
    _law(
        "mass_percent_solvent",
        "solutions",
        ("mass percent", "percent by mass", "mass percentage"),
        "percent",
        (
            var("solute_mass", "m", "gram", words=_SOLUTE_WORDS, needs_words=True),
            var("solvent_mass", "m", "gram", words=_SOLVENT_WORDS, needs_words=True),
        ),
    ),
    _law(
        "particles_to_mass",
        "amounts",
        _GRAMS_ASKS,
        "gram",
        (
            # Molecules, not atoms: 3.01e23 atoms of O2 are half as many molecules.
            var(
                "particles",
                "N",
                dimensionless=True,
                words=("molecules", "particles", "formula units"),
                needs_words=True,
            ),
            _molar_mass(),
        ),
        species="compound",
    ),
    _law(
        "mole_fraction",
        "solutions",
        # The asked part is the solute: "the mole fraction of water" is not this reading.
        ("mole fraction of compound", "mole fraction of the compound"),
        "dimensionless",
        (
            var("moles_a", "nA", "mole", words=_SOLUTE_WORDS, needs_words=True),
            var("moles_b", "nB", "mole", words=_SOLVENT_WORDS, needs_words=True),
        ),
    ),
    _law(
        "gas_density",
        "gases",
        ("density",),
        "gram / liter",
        (var("pressure", "P", "atmosphere"), _molar_mass(), var("temperature", "T", "kelvin")),
        cues=("gas",),
        species="compound",
    ),
    _law(
        "molar_mass_from_density",
        "gases",
        ("molar mass",),
        "gram / mole",
        (
            var("density", "d", "gram / liter"),
            var("temperature", "T", "kelvin"),
            var("pressure", "P", "atmosphere"),
        ),
        cues=("gas",),
    ),
    _law(
        "percent_ionization",
        "acid_base",
        ("percent ionization", "percentage ionization", "% ionization", "percent dissociation"),
        "percent",
        (_concentration(), var("ka", "Ka", dimensionless=True, words=("k_a",), needs_words=True)),
        species="acid_weak",
    ),
    _law(
        "reaction_heat",
        "thermochemistry",
        ("how much heat", "heat", "energy"),
        "kilojoule",
        (var("moles", "n", "mole"), var("enthalpy", "ΔH", "kilojoule / mole")),
        nonnegative=False,
    ),
    _law(
        "electrolysis_time",
        "electrochemistry",
        ("how long", "time"),
        "second",
        (
            var("mass", "m", "gram"),
            var(
                "electrons",
                "n",
                dimensionless=True,
                words=("n =", "electrons"),
                needs_words=True,
                fallback="ion_charge",
            ),
            var("current", "I", "ampere"),
            var("molar_mass", "M", "gram / mole", fallback="deposited_molar_mass"),
        ),
        cues=("deposit", "electrolysis", "plated", "plating"),
    ),
)

LAWS: tuple[ChemistryLaw, ...] = (
    *ACID_BASE,
    *SOLUTIONS,
    *AMOUNTS,
    *KINETICS,
    *ELECTROCHEMISTRY,
    *THERMOCHEMISTRY,
    *ANALYSIS,
    *FORMULA_LAW_BINDINGS,
)
