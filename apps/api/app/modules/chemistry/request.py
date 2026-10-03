"""Chemistry request gating and compound-name extraction.

The gate is a cheap classifier that runs on every chat turn, so it must stay
linear on hostile input and must not claim everyday language. Numeric/formula
extraction belongs in ``extract.py`` so this gate cannot accidentally solve.

Cues come in three strengths:

* strong: a phrase only chemistry uses ("molar mass", "titration", "ΔH");
* case-sensitive symbols (``pH``, ``Ka``, ``Kp``) that lose meaning in lowercase;
* weak single words ("acid", "boiling", "nuclear", "mole") that also appear in
  cooking, weather and politics. Weak cues count only in pairs, or next to a
  formula such as ``H2SO4``.
"""

from __future__ import annotations

import re

from app.modules.chemistry.species import ARROWS
from app.modules.chemistry.species_facts import is_formula

# Formula characters are case-sensitive on purpose. Under ``re.IGNORECASE`` a
# lowercase word such as "sodium" splits into "so" + "di" + "um" in Fibonacci-many
# ways, which made a 32-letter run cost seconds. Callers keep their own flags for
# the words around a formula; ``(?-i:…)`` pins only the formula itself.
CHEMICAL_FORMULA = (
    r"(?-i:(?:e-|[A-Z][a-z]?[0-9]*(?:\([A-Za-z0-9]+\)[0-9]*)*"
    r"(?:[A-Z][a-z]?[0-9]*(?:\([A-Za-z0-9]+\)[0-9]?)?)*)"
    r"(?:\^(?:\{\d*[+-]\}|\d*[+-])|\d*[+-])?"
    r"(?:\((?:aq|s|l|g)\))?)"
)
_ARROW = "(?:" + "|".join(re.escape(arrow) for arrow in ARROWS) + ")"
# Coefficients stop at two digits so a nuclide such as 238U is not "238 U".
_TERM = rf"(?:\d{{1,2}}\s*)?{CHEMICAL_FORMULA}"
# A match may not start inside a token ("CuSO4.5H2O" must not truncate to
# "H2O -> …") and may not end where a bracket, hydrate dot or digit continues.
# A period that ends a sentence ("… -> H2O.") is still allowed.
EQUATION_RE = re.compile(
    rf"(?<![A-Za-z0-9·\[])(?<![A-Za-z0-9]\.)"
    rf"((?:{_TERM}\s*\+\s*)*{_TERM}\s*{_ARROW}\s*(?:{_TERM}\s*\+\s*)*{_TERM})"
    rf"(?![A-Za-z0-9·\]]|\.\d)"
)

# Longest message the gate reads. The head and tail windows keep a question that
# follows a long pasted passage without scanning 32k characters.
_GATE_WINDOW = 2000

_STRONG_CUE = re.compile(
    r"\b(?:stoichiometr\w*|molar\s+(?:mass|volume|absorptivity|concentration)|"
    r"molarity|molality|formula\s+units?|M1V1|mass\s+percent|pOH|"
    r"thermochem\w*|enthalpy|specific\s+heat|calorimet\w*|"
    r"reaction\s+quotient|equilibrium\s+(?:constant|expression)|ice\s+(?:table|equilibrium)|"
    r"rate\s+(?:constant|law)|first[- ]order|second[- ]order|zero[- ]order|arrhenius|"
    r"electrochem\w*|nernst|electrolysis|cell\s+potential|faraday'?s?\s+law|"
    r"galvanic|radioactive|nuclear\s+(?:equation|mass|activity)|decay\s+constant|"
    r"exponential\s+decay|mass\s+defect|binding\s+energy|electron\s+capture|"
    r"beer[- ]lambert|absorbance|percent\s+(?:yield|composition|error)|avogadro|"
    r"pv\s*=\s*nrt|ideal\s+gas|gas\s+law|combined\s+gas|partial\s+pressure|"
    r"molecular\s+descriptor|logp|tpsa|periodic\s+table|atomic\s+(?:mass|number|weight)|"
    r"electronegativity|electron\s+configuration|valence\s+electrons?|"
    r"empirical\s+formula|molecular\s+formula|titration|ksp|hess'?s?\s+law|vsepr|"
    r"lewis\s+(?:structure|dot)|formal\s+charge|oxidation\s+(?:state|number)|"
    r"(?:boyle|charles|dalton|graham|henry)'?s?\s+law|clausius|functional\s+groups?|isomer\w*|"
    r"coordination\s+(?:complex|compound|number)|polyprotic|common[- ]ion|"
    r"bond\s+enthalpy|formation\s+enthalpy|weak\s+(?:acid|base)|strong\s+(?:acid|base)|"
    r"boiling[- ]point\s+elevation|freezing[- ]point\s+depression|osmotic\s+pressure|raoult|"
    r"gas\s+collected\s+over\s+water|precipitation\s+reaction|stereochemistry|"
    r"crystal\s+field|magnetic\s+moment|standard\s+deviation|standard\s+error|"
    r"relative\s+uncertainty|retention\s+factor|Michaelis[- ]Menten|IUPAC|"
    r"IR\s+(?:ranges|peak)|NMR\s+(?:ranges|peak|splitting)|molecular\s+ion|"
    r"HBr\s+addition|bromine\s+addition|acid\s+hydration|hydroxide\s+substitution|"
    r"esterification|calibration\s+curve|gravimetric|standard\s+addition|"
    r"calorimeter\s+constant|gibbs\s+(?:free\s+)?energy|Δ[GHS]|delta\s*[GHS](?=\s*=))\b",
    re.IGNORECASE,
)
# "Chemistry" names the subject, except in the idiom for getting along ("great chemistry").
_SUBJECT_CUE = re.compile(r"\bchemistry\b", re.IGNORECASE)
_CHEMISTRY_IDIOM = re.compile(
    r"\b(?:great|good|bad|no|real|instant|amazing|natural|undeniable|zero|romantic|"
    r"on-?screen|team|special|incredible)\s+chemistry\b(?!\s+(?:textbook|book|teacher|"
    r"class|course|homework|question|problem|tutor|lab|notes?|exam|test|lesson)s?\b)|"
    r"\bchemistry\s+(?:between|together)\b|"
    r"\bchemistry\s+with\s+(?:him|her|them|you|me|us|each\s+other|someone)\b",
    re.IGNORECASE,
)
# A battery or a habit has a half-life too: chemistry's has a number, a nuclide or a decay.
_HALF_LIFE = re.compile(r"\bhalf[- ]life\b", re.IGNORECASE)
_DECAY_CONTEXT = re.compile(
    r"\d|\b(?:decay\w*|radioactiv\w*|isotopes?|nuclides?|first[- ]order|reaction|"
    r"sample|rate\s+constant)\b",
    re.IGNORECASE,
)
# "the shape of NH3": a shape is chemistry's only when what it is of is a real formula.
_SHAPE_OF = re.compile(
    r"\b(?:shape|geometry)\s+of\s+(?:an?\s+|the\s+)?([A-Z][A-Za-z0-9()]*)(?![A-Za-z0-9(])",
    re.IGNORECASE,
)
# "Ka", "Kb", "pH", "Rf" and "Kp" are words in lowercase ("kb" file size, "ph.d.").
_SYMBOL_CUE = re.compile(
    r"(?<![A-Za-z0-9])(?:pH|pOH|pKa|pKb|Ka|Kb|Kc|Kp|Qc|Ksp|Rf|Δ[GHS])(?![A-Za-z])"
)
_WEAK_CUE = re.compile(
    r"\b(?:acid|base|boiling|freezing|nuclear|mol(?:e|es)?|molecules?|molar|dilut\w*|buffer|"
    r"equilibrium|entropy|kinetic\w*|empirical|oxidation|coordination|calibration|"
    r"precipitation|gibbs|faraday|hess|boyle|charles|dalton|lewis|reaction|compound|"
    r"chemical|atoms?|bond)\b",
    re.IGNORECASE,
)
# An element followed by a digit ("H2O", "CO2", "Fe2") or a capital run ("NaOH").
_FORMULA_HINT = re.compile(r"\b[A-Z][a-z]?\d|\b(?:[A-Z][a-z]?){2,4}\b")
_BALANCE_CUE = re.compile(r"\b(?:balance|balanced|coefficient)\b", re.IGNORECASE)
_EQUATION_WORDS = re.compile(
    r"\b(?:moles?|grams?|limiting|yield)\b|(?<![A-Za-z0-9])(?:Kc|Qc)(?![A-Za-z])",
    re.IGNORECASE,
)

# The user asked about a molecule, so any name-shaped phrase after these is a lookup.
_EXPLICIT_NAME_RE = re.compile(
    r"\b(?:(?:lewis\s+)?structure\s+of|molecular\s+formula\s+of|formula\s+of|"
    r"draw\s+(?:the\s+)?(?:lewis\s+)?structure\s+of|"
    r"show(?:\s+me)?\s+(?:the\s+)?(?:lewis\s+)?structure\s+of|"
    r"draw\s+(?:the\s+)?molecule|show\s+me\s+(?:the\s+)?molecule|"
    r"describe(?:\s+the)?\s+molecule|smiles\s+for|smiles\s+of|"
    r"chemical\s+structure\s+of|the\s+compound|"
    r"(?:log\s*p|tpsa|polar\s+surface\s+area|drug[-\s]?likeness)\s+(?:of|for))\s*"
    r"([a-zA-Z][a-zA-Z0-9\-\s]{2,40}?)"
    r"(?:\?|$|\.|,|\s+(?:and|or|with|in|at|for|to|is|are|the)\b)",
    re.IGNORECASE,
)
# Bare "what is X" is ordinary language ("what is love"), so X must look like a
# compound: a common name or a systematic ending.
_BARE_NAME_RE = re.compile(
    r"\b(?:what\s+is|what's|tell\s+me\s+about|describe(?:\s+the)?|draw|show\s+me)\s+"
    r"([a-zA-Z][a-zA-Z0-9\-\s]{2,40}?)"
    r"(?:\?|$|\.|,|\s+(?:and|or|with|in|at|for|to|is|are|the)\b)",
    re.IGNORECASE,
)
_COMMON_COMPOUNDS = frozenset(
    {
        "aspirin",
        "caffeine",
        "ibuprofen",
        "paracetamol",
        "acetaminophen",
        "penicillin",
        "insulin",
        "morphine",
        "nicotine",
        "dopamine",
        "serotonin",
        "adrenaline",
        "epinephrine",
        "cholesterol",
        "glucose",
        "fructose",
        "sucrose",
        "lactose",
        "ammonia",
        "methane",
        "ethane",
        "propane",
        "butane",
        "pentane",
        "hexane",
        "ethylene",
        "propylene",
        "acetylene",
        "benzene",
        "toluene",
        "phenol",
        "aniline",
        "ethanol",
        "methanol",
        "propanol",
        "glycerol",
        "glycerin",
        "acetone",
        "urea",
        "formaldehyde",
        "acetaldehyde",
        "chloroform",
        "menthol",
        "vanillin",
        "retinol",
        "adenosine",
        "adenine",
        "guanine",
        "cytosine",
        "thymine",
        "uracil",
        "dna",
        "glycine",
        "alanine",
        "cysteine",
        "tryptophan",
        "histamine",
        "melatonin",
        "testosterone",
        "estradiol",
        "cortisol",
        "capsaicin",
        "limonene",
        "camphor",
        "naphthalene",
        "ozone",
        "hydrogen peroxide",
        "salt",
        "sugar",
        "vinegar",
    }
)
_COMPOUND_ENDINGS = (
    "oxide",
    "dioxide",
    "chloride",
    "bromide",
    "iodide",
    "fluoride",
    "sulfate",
    "sulfite",
    "sulfide",
    "nitrate",
    "nitrite",
    "hydroxide",
    "carbonate",
    "bicarbonate",
    "phosphate",
    "acetate",
    "cyanide",
    "peroxide",
    "acid",
    "amine",
    "amide",
    "ester",
    "ether",
    "ketone",
    "aldehyde",
    "alcohol",
    "glycol",
)
_NAME_STOPWORDS = frozenset(
    {
        "the",
        "of",
        "a",
        "an",
        "and",
        "for",
        "to",
        "in",
        "on",
        "at",
        "with",
        "from",
        "about",
        "this",
        "that",
        "your",
        "my",
        "you",
        "me",
        "it",
        "is",
        "are",
    }
)
_FALSE_POSITIVES = frozenset(
    {
        "the",
        "this",
        "that",
        "it",
        "a",
        "an",
        "light",
        "energy",
        "time",
        "space",
        "code",
        "data",
        "file",
        "image",
        "text",
    }
)
# "compound interest", "compound sentence": not a chemical compound.
_NOT_A_COMPOUND = re.compile(
    r"\bcompound\s+(?:interest|word|sentence|noun|fracture|growth|annual|return|verb|eye)\b",
    re.IGNORECASE,
)
_STRUCTURE_VERB = re.compile(
    r"\b(?:structure|formula|what\s+is|tell\s+me\s+about|draw|show|describe)\b", re.IGNORECASE
)
_STRUCTURE_NOUN = re.compile(
    r"\b(?:molecules?|smiles|molecular|chemical|compounds?)\b", re.IGNORECASE
)


def _window(content: str) -> str:
    cleaned = content.strip()
    if len(cleaned) <= 2 * _GATE_WINDOW:
        return cleaned
    return f"{cleaned[:_GATE_WINDOW]}\n{cleaned[-_GATE_WINDOW:]}"


def _has_equation(text: str) -> bool:
    return re.search(_ARROW, text) is not None and EQUATION_RE.search(text) is not None


def is_chemistry_question(content: str) -> bool:
    """True for supported calculations or plausible compound lookup requests."""
    cleaned = _window(content)
    if not cleaned:
        return False
    if _STRONG_CUE.search(cleaned) or _SYMBOL_CUE.search(cleaned):
        return True
    if _SUBJECT_CUE.search(cleaned) and not _CHEMISTRY_IDIOM.search(cleaned):
        return True
    if _HALF_LIFE.search(cleaned) and _DECAY_CONTEXT.search(cleaned):
        return True
    shape = _SHAPE_OF.search(cleaned)
    if shape is not None and is_formula(shape.group(1)):
        return True
    weak = {match.group(0).lower() for match in _WEAK_CUE.finditer(cleaned)}
    if len(weak) >= 2 or (weak and _FORMULA_HINT.search(cleaned)):
        return True
    if _has_equation(cleaned) and (_BALANCE_CUE.search(cleaned) or _EQUATION_WORDS.search(cleaned)):
        return True
    if _NOT_A_COMPOUND.search(cleaned):
        return False
    if _STRUCTURE_VERB.search(cleaned) and _STRUCTURE_NOUN.search(cleaned):
        return True
    if extract_compound_name(cleaned) is not None:
        return True
    # "How many moles are in 36 g of water?" names no cue word, but reads as one law.
    from app.modules.chemistry.binding import bind_chemistry_intent

    return bind_chemistry_intent(cleaned) is not None


def _clean_name(raw: str) -> str | None:
    name = raw.strip().lower()
    name = re.sub(r"\s+(?:the|a|an|of|for|with)$", "", name).strip()
    name = re.sub(r"^(?:the\s+)?(?:lewis\s+)?structure\s+of\s+", "", name).strip()
    name = re.sub(r"^(?:molecule|compound)\s+", "", name).strip()
    if not name or name in _FALSE_POSITIVES or not 3 <= len(name) <= 40:
        return None
    words = name.split()
    # "what is the capital of France" matches the same lead as "what is aspirin".
    # A real compound name has no function words.
    if len(words) > 3 or any(word in _NAME_STOPWORDS for word in words):
        return None
    return name


def _looks_like_compound(name: str) -> bool:
    if name in _COMMON_COMPOUNDS:
        return True
    return any(
        word in _COMMON_COMPOUNDS or word.endswith(_COMPOUND_ENDINGS) for word in name.split()
    )


def extract_compound_name(content: str) -> str | None:
    """Return a conservative PubChem lookup candidate."""
    if _NOT_A_COMPOUND.search(content):
        return None
    explicit = _EXPLICIT_NAME_RE.search(content)
    if explicit is not None:
        return _clean_name(explicit.group(1))
    bare = _BARE_NAME_RE.search(content)
    if bare is None:
        return None
    name = _clean_name(bare.group(1))
    if name is None or not _looks_like_compound(name):
        return None
    return name
