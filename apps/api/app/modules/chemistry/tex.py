# ruff: noqa: RUF001, RUF002, RUF003 -- chemistry text is read glyph by glyph: −, ×, ₂, ⁺.
"""A chemistry row as maths, laid out as physics' and maths' rows are.

A solver writes its rows as ASCII text (``n = 36 g / 18.015 g/mol``, ``M(H2O) = 18.015
g/mol``, ``pH = −log10(0.001)``). A worked reply shows every state as maths, whatever the
subject: symbols in the maths font, a unit upright after a thin space (``\\,\\mathrm{g/mol}``),
a chemical formula upright (``\\mathrm{H₂O}``), so ``n(H₂O)`` never reads as n times H
times O. ``chemistry_tex`` writes that LaTeX, or None for a row that is not one formula:
a sentence ("limiting reagent = O2 (fewest reaction units)"), an equation with an arrow, a
list. Such a row stays text, as before; nothing is guessed.

The row is typeset first (``notation.typeset``: subscripts, charges, the true minus), then
read token by token. Inside an upright run the phone draws Unicode sub- and superscripts as
written (``lib/math/latexPreprocess.ts``), so a formula keeps its own glyphs.
"""

from __future__ import annotations

import re

from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.notation import typeset

_SUBSCRIPTS = dict(zip("₀₁₂₃₄₅₆₇₈₉ₐₑₒₓₜᵢⱼₙₘₖₗₚₛ", "0123456789aeoxtijnmklps", strict=True))
_SUPERSCRIPTS = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-", strict=True))
_CHARGE = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]*[⁺⁻]$")
# Units a solver writes after a number, longest first so "mol" is not read as "m".
_UNIT_ATOMS = sorted(
    (
        "mmHg kcal nucleon particles particle molecules molecule atoms atom electrons kPa MeV "
        "MHz mmol µmol mol mL µL dL kg mg µg kJ cal atm bar Pa torr Torr min ms mV mA cm mm "
        "nm dm km ppm ppb BM Hz °C °F ° g L M K J s h V A C F m u T W N Ω"
    ).split(),
    key=len,
    reverse=True,
)
_UNIT_ATOM = "|".join(re.escape(atom) for atom in _UNIT_ATOMS)
_POWER = r"(?:⁻?[¹²³])?"
_UNIT_GROUP = rf"(?:{_UNIT_ATOM}){_POWER}(?:·(?:{_UNIT_ATOM}){_POWER})*"
_UNIT = re.compile(rf"(?:{_UNIT_GROUP})(?:/(?:\((?:{_UNIT_GROUP})\)|{_UNIT_GROUP}))*(?![\w°])")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_RAISED = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻"
_DIGITS = "0123456789"
# "× 10⁻⁵" after a number: scientific notation; "10⁻⁴" alone: a power of ten.
_TEN_POWER = re.compile(rf"\s*×\s*10([{_RAISED}]+)")
_BARE_TEN = re.compile(rf"10([{_RAISED}]+)")
_FUNCTIONS = {"ln": r"\ln", "log": r"\log", "exp": r"\exp", "log₁₀": r"\log_{10}"}
# What a symbol's lowercase letters after a capital stand for, when they are its subscript:
# K_a, M_b, X_i, N_e (one letter), P_total, E°_cell, ΔH_vap (a word of the notation). Any
# other letter is a symbol of its own (``MIt`` is M·I·t), and any other word is prose.
_SINGLE_TAILS = frozenset("abcdefimnpswx")
_TAIL_WORDS = frozenset(
    {
        "sp", "total", "cal", "dry", "water", "vap", "fus", "sub", "rxn", "cell", "cathode",
        "anode", "max", "std", "spike", "sample", "eq", "obs", "mix", "sys", "surr", "net",
    }
)  # fmt: skip
# One element with a count is a species only for an element that comes as molecules.
_MOLECULAR_ELEMENTS = frozenset({"H₂", "N₂", "O₂", "F₂", "Cl₂", "Br₂", "I₂", "O₃", "P₄", "S₈"})
_STATE = re.compile(r"\((?:s|l|g|aq)\)$")
# Words a quantity is of, in brackets after its symbol: m(solute), V(solution).
_ROLE_WORDS = frozenset({"solute", "solvent", "solution", "products", "reactants", "sample"})
_OPERATORS = {"=": " = ", "+": " + ", "-": " - ", "−": " - ", "×": r" \times ", "≈": r" \approx "}
# A calculation with no relation in it: "√(32 / 7)", "|9.8 − 10| / |10| × 100".
_OPERATION = re.compile(r"[×/+√]|\d\s*[−-]\s*[\d(]")
_ELEMENT_SHARE = re.compile(r"([A-Z][a-z]?) = (\d+(?:\.\d+)?)%")
# Short words a sentence holds: one of them makes the row prose ("14 at 25 °C").
_PROSE_WORDS = frozenset(
    {"in", "at", "of", "to", "is", "or", "on", "by", "as", "if", "so", "an", "and", "for", "per"}
)
_UNARY_MINUS = re.compile(r"(^|[=(\[{]|\\times) ?- ")
# A symbol numbered from one (C₁V₁ = C₂V₂): C₂ there is a symbol, not a formula.
_INDEXED = re.compile(r"[A-Z][a-z]?₁(?![₀-₉])")


class _NotMaths(Exception):
    """The row is not one formula: it stays text."""


def law_symbols(formula: str) -> frozenset[str]:
    """The symbols a law is written in (``BO = (Nb − Na) / 2``: BO, Nb, Na), so a row of the
    same result reads them as symbols, never as the element they spell (Na, sodium). What a
    quantity is of (``n(H2O)``, ``[H+]``) and a counted formula are no symbols."""
    text = re.sub(r"(?<=[\w°])\([^()]*\)|\[[^\]]*\]", " ", typeset(formula))
    return frozenset(
        token for token in re.findall(r"[^\W\d_][\w°]*", text) if not re.search(r"[₀-₉⁺⁻]", token)
    )


def chemistry_tex(row: str, symbols: frozenset[str] = frozenset()) -> str | None:
    """``row`` (a solver's ASCII text) as LaTeX, or None when it is not one formula: a
    relation (``n = m / M``) or a calculation (``√(32 / 7)``), never a bare token (``2H``).
    ``symbols``: the law's own (``law_symbols``)."""
    text = typeset(row.strip())
    if "=" not in text and _OPERATION.search(text) is None:
        return None
    share = _ELEMENT_SHARE.fullmatch(text)
    if share is not None and share.group(1) in BY_SYMBOL:
        # "C = 40.0%": carbon's share of the mass, not a variable C.
        return rf"{species_tex(share.group(1))} = {share.group(2)}\,\%"
    return _read(text, symbols)


def symbol_tex(text: str, symbols: frozenset[str] = frozenset()) -> str | None:
    """One quantity's symbol (``Kc``, ``pH``, ``[H+]``, ``t₁/₂``) as LaTeX, or None."""
    shown = typeset(text.strip())
    if not shown or " " in shown:
        return None
    return _read(shown, symbols)


def _read(text: str, symbols: frozenset[str]) -> str | None:
    if not text:
        return None
    try:
        reader = _Reader(text, indexed=_INDEXED.search(text) is not None, symbols=symbols)
        tex = reader.expression()
    except _NotMaths:
        return None
    # A sign after a relation, a bracket or a product is the number's own: "= -40".
    return _UNARY_MINUS.sub(_signed, re.sub(r"\s+", " ", tex)).strip() or None


def _signed(match: re.Match[str]) -> str:
    before = match.group(1)
    return f"{before} -" if before in ("=", "\\times") else f"{before}-"


def is_species(token: str, *, indexed: bool = False) -> bool:
    """A chemical formula as written: element symbols with their counts and a charge,
    ``H₂O``, ``NaCl``, ``Fe²⁺``, ``(NH₄)₂SO₄``. One element of one letter is a symbol (``C`` is
    a concentration as often as carbon), and one with a count only an element that comes as
    molecules (``O₂``, not ``V₂``). ``indexed``: the row numbers its symbols (``C₁V₁``), so
    a token counted alike throughout (``C₂V₂``) is symbols too."""
    body = _CHARGE.sub("", token)
    if body != token:
        return bool(body) and _elements_only(body)
    if not _elements_only(body):
        return False
    letters = re.findall(r"[A-Z][a-z]?", body)
    counts = set(re.findall(r"[₀-₉]+", body))
    if indexed and len(counts) == 1 and len(next(iter(counts))) == 1:
        return False
    if "₁" in counts:
        return False
    if len(letters) > 1:
        return True
    return body in _MOLECULAR_ELEMENTS if counts else len(letters[0]) == 2


def _elements_only(body: str) -> bool:
    letters = re.findall(r"[A-Z][a-z]?", body)
    leftover = re.sub(r"[A-Z][a-z]?|[₀-₉]|[()\[\]]", "", body)
    return bool(letters) and not leftover and all(symbol in BY_SYMBOL for symbol in letters)


def species_tex(token: str) -> str:
    return rf"\mathrm{{{token}}}"


def unit_tex(unit: str) -> str:
    """``g/mol`` → ``\\,\\mathrm{g/mol}``; ``°C`` → ``\\,^\\circ\\mathrm{C}``."""
    if unit == "°":
        return r"^\circ"
    if unit.startswith("°"):
        return rf"\,^\circ\mathrm{{{unit[1:]}}}"
    return rf"\,\mathrm{{{unit}}}"


def _script(glyphs: str) -> str:
    return "".join(_SUPERSCRIPTS.get(char, _SUBSCRIPTS.get(char, char)) for char in glyphs)


def _bracketed_species(inner: str) -> bool:
    """``[H⁺]``, ``[HA]``, ``[A⁻]``, ``[N₂O₄]``: what a concentration is of, any letters."""
    return re.fullmatch(rf"(?:[A-Z][a-z]?[₀-₉]*|\(|\))+[{_RAISED}]*", inner) is not None


def _in_word(text: str, at: int) -> bool:
    """Whether the glyph at ``at`` goes on a symbol or formula: letters, digits, subscripts,
    °, a charge (``Fe²⁺``: raised digits only before their sign), a slash between subscripts
    (``t₁/₂``)."""
    char = text[at]
    if (char.isascii() and char.isalnum()) or char in _SUBSCRIPTS or char in "°_Δ\u0304⁺⁻":
        return True
    if char in _RAISED:
        rest = text[at:].lstrip("⁰¹²³⁴⁵⁶⁷⁸⁹")
        return rest[:1] in ("⁺", "⁻")
    if char == "/":
        return text[at - 1] in _SUBSCRIPTS and text[at + 1 : at + 2] in _SUBSCRIPTS
    return char.isalpha()


def _matching(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == opening:
            depth += 1
        elif text[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    raise _NotMaths


class _Reader:
    """One pass over a typeset row; raises ``_NotMaths`` at anything that is not maths."""

    def __init__(self, text: str, *, indexed: bool, symbols: frozenset[str]) -> None:
        self.text = text
        self.at = 0
        self.indexed = indexed
        self.symbols = symbols

    def inner(self, text: str) -> str:
        return _Reader(text, indexed=self.indexed, symbols=self.symbols).expression()

    def expression(self) -> str:
        out: list[str] = []
        while self.at < len(self.text):
            out.append(self.token())
        return "".join(out)

    def token(self) -> str:
        char = self.text[self.at]
        if char == " ":
            self.at += 1
            return " "
        if char in _DIGITS:
            return self.number()
        if char in "([":
            return self.group(char)
        if char in "|/":
            self.at += 1
            return char
        if char == "^":
            self.at += 1
            return f"^{{{self.argument()}}}"
        if char == "√":
            self.at += 1
            return rf"\sqrt{{{self.argument()}}}"
        if char in _RAISED:
            return self.superscript()
        if char in _OPERATORS:
            self.at += 1
            return _OPERATORS[char]
        if char in "ΣΠ" and self.text[self.at + 1 : self.at + 2] in ("", " "):
            self.at += 1
            return r"\Sigma " if char == "Σ" else r"\Pi "
        if char == "Δ" or char.isalpha():
            return self.word()
        raise _NotMaths

    def number(self) -> str:
        match = _NUMBER.match(self.text, self.at)
        if match is None:
            raise _NotMaths
        self.at = match.end()
        shown = match.group(0)
        bare = _BARE_TEN.match(self.text, match.start()) if shown == "10" else None
        power = _TEN_POWER.match(self.text, self.at)
        if bare is not None:
            self.at = bare.end()
            shown = f"10^{{{_script(bare.group(1))}}}"
        elif power is not None:
            self.at = power.end()
            shown = rf"{shown} \times 10^{{{_script(power.group(1))}}}"
        if self.text.startswith("%", self.at):
            self.at += 1
            return rf"{shown}\,\%"
        return shown + self.unit()

    def unit(self) -> str:
        """The unit after a number, then a species it counts (``4.0 mol H₂O``)."""
        if not self.text.startswith(" ", self.at):
            return ""
        match = _UNIT.match(self.text, self.at + 1)
        if match is None:
            return ""
        self.at = match.end()
        shown = unit_tex(match.group(0))
        counted = re.match(r" ([^\s,;)\]]+)", self.text[self.at :])
        if counted is not None and (
            counted.group(1) == "e⁻" or is_species(counted.group(1), indexed=self.indexed)
        ):
            self.at += len(counted.group(0))
            shown += rf"\ {species_tex(counted.group(1))}"
        return shown

    def group(self, opening: str) -> str:
        closing = ")" if opening == "(" else "]"
        end = _matching(self.text, self.at, opening, closing)
        inner = self.text[self.at + 1 : end]
        self.at = end + 1
        body = species_tex(inner) if opening == "[" and _bracketed_species(inner) else None
        return f"{opening}{body or self.inner(inner)}{closing}{self.subscript()}"

    def argument(self) -> str:
        """What a caret or root applies to: a bracketed group, or one token."""
        char = self.text[self.at : self.at + 1]
        if char and char in "([{":
            closing = {"(": ")", "[": "]", "{": "}"}[char]
            end = _matching(self.text, self.at, char, closing)
            inner = self.text[self.at + 1 : end]
            self.at = end + 1
            return self.inner(inner)
        match = re.compile(r"-?[\w.]+").match(self.text, self.at)
        if match is None:
            raise _NotMaths
        self.at = match.end()
        return self.inner(match.group(0))

    def superscript(self) -> str:
        start = self.at
        while self.at < len(self.text) and self.text[self.at] in _RAISED:
            self.at += 1
        return f"^{{{_script(self.text[start : self.at])}}}"

    def subscript(self) -> str:
        """Unicode subscripts straight after a bracket: ``[A]₀``, ``[A]ₜ``."""
        start = self.at
        while self.at < len(self.text) and self.text[self.at] in _SUBSCRIPTS:
            self.at += 1
        script = _script(self.text[start : self.at])
        return f"_{{{script}}}" if script else ""

    def word(self) -> str:
        start = self.at
        while self.at < len(self.text) and (
            self.text[self.at].isalnum() or self.text[self.at] in "°_Δ̄⁺⁻/"
        ):
            # A slash belongs to a word only between subscripts: t₁/₂.
            if self.text[self.at] == "/" and not (
                self.text[self.at - 1] in _SUBSCRIPTS
                and self.text[self.at + 1 : self.at + 2] in _SUBSCRIPTS
            ):
                break
            self.at += 1
        base_e = self.text[self.at - 1 : self.at] == "e" and self.at - start > 1
        if base_e and self.text.startswith("^", self.at):
            self.at -= 1  # "Ae^(−Ea/RT)": e is the exponential's base
        token = self.text[start : self.at]
        if token in _PROSE_WORDS:
            raise _NotMaths
        if token in _FUNCTIONS:
            return f"{_FUNCTIONS[token]} "
        if self.text.startswith("(", self.at) and (of := self._of()):
            return f"{_symbols(token)}{of}"
        if re.fullmatch(r"[A-Z]{3,}", token):
            return species_tex(token)  # an abbreviation named in capitals: LOD, CFSE
        if token in ("pH", "pOH"):
            return species_tex(token)
        if token.startswith("pK"):
            return rf"\mathrm{{p}}{_symbols(token[1:])}"
        if token in self.symbols:
            return _symbols(token)
        if is_species(token, indexed=self.indexed):
            return species_tex(token)
        if re.fullmatch(r"[A-Za-z][⁰¹²³⁴⁵⁶⁷⁸⁹]*[⁺⁻]", token):
            return species_tex(token)  # a generic ion: A⁻, e⁻
        return _symbols(token)

    def _of(self) -> str:
        """``(H₂O)`` or ``(solute)`` after a symbol: what the quantity is of, upright."""
        end = _matching(self.text, self.at, "(", ")")
        inner = self.text[self.at + 1 : end]
        named = _STATE.sub("", inner)
        generic = _bracketed_species(named) and not re.fullmatch(r"[A-Z][a-z]?[₀-₉]+", named)
        if is_species(named) or named in BY_SYMBOL or named == "e⁻" or generic:
            self.at = end + 1
            return f"({species_tex(inner)})"
        if inner in _ROLE_WORDS:
            self.at = end + 1
            return rf"(\text{{{inner}}})"
        return ""


def _scripted(char: str) -> bool:
    """A glyph of a symbol's subscript: a digit, a Unicode subscript, the slash of t₁/₂."""
    return char in _DIGITS or char in _SUBSCRIPTS or char == "/"


def _symbols(token: str) -> str:
    """Symbols written side by side, each as maths: ``iMRT``, ``Ka₁`` → ``K_{a1}``,
    ``E°cell`` → ``E^\\circ_{cell}``, ``ΔHvap`` → ``\\Delta H_{vap}``, ``x̄`` → ``\\bar{x}``,
    ``t₁/₂`` → ``t_{1/2}``. A word is prose, never symbols: the row stays text."""
    out: list[str] = []
    at = 0
    while at < len(token):
        delta = token[at] == "Δ"
        at += delta
        if at >= len(token) or not token[at].isalpha():
            raise _NotMaths
        base = token[at]
        at += 1
        if base.isascii() and base.islower() and re.match(r"[a-z]{2}", token[at:]):
            raise _NotMaths  # "mass", "rate", "slope": a word
        bar = token.startswith("̄", at)
        at += bar
        circle = token.startswith("°", at)
        at += circle
        script = ""
        tail = re.match(r"[a-z]+", token[at:]) if base.isupper() else None
        if tail is not None:
            letters = tail.group(0)
            if letters in _TAIL_WORDS or letters in _SINGLE_TAILS:
                script, at = letters, at + tail.end()
            elif len(letters) > 1:
                raise _NotMaths  # "Formula", "Mass": a word
        if not circle and token.startswith("°", at):
            circle, at = True, at + 1
        explicit = re.match(r"_([A-Za-z0-9]+)", token[at:])
        if explicit is not None:
            script, at = script + explicit.group(1), at + explicit.end()
        while at < len(token) and _scripted(token[at]):
            script += _SUBSCRIPTS.get(token[at], token[at])
            at += 1
        shown = (r"\Delta " if delta else "") + (rf"\bar{{{base}}}" if bar else base)
        shown += r"^\circ" if circle else ""
        shown += f"_{{{script}}}" if script else ""
        out.append(shown)
    return " ".join(out)
