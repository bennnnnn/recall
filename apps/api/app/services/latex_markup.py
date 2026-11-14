# ruff: noqa: RUF001 -- the point of this module is the Greek letters and signs markup names.
"""A question written in LaTeX markup, read as the plain text a student types.

A worksheet or a model's reply pasted into the chat carries its markup:
``\\(q_1 = +2.0 \\, \\mu\\text{C}\\)``, ``\\(12.0 \\text{ V}\\)``, ``R_1 = 4.0 \\, \\Omega``,
``\\(\\mu_k = 0.30\\)``. The subject readers read numbers, units and words, so such a
question was read as no question at all and went to the model, though its plain twin
("q1 = +2.0 μC", "12.0 V", "R1 = 4.0 Ω") was verified (phone test, 2026-11-11).

``without_markup`` writes the markup as that plain text, once, where a subject reads the
message; the model still sees what the user wrote. It changes only markup: a delimiter, a
text or upright run, a space command, a Greek letter or a sign named by its command, a
braced script, a fraction or a root. A command it does not know is left as written, and
text with no markup comes back unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Runs whose content is read as written: "\text{ m/s}", "\mathrm{kg}", "\ce{H2O}".
_WRAPPERS = frozenset(
    {
        "text",
        "textrm",
        "textnormal",
        "textit",
        "textbf",
        "textsf",
        "mathrm",
        "mathit",
        "mathbf",
        "mathsf",
        "mathnormal",
        "mbox",
        "operatorname",
        "ce",
        "pu",
        "unit",
        "si",
    }
)
# Commands that space or size, and the bracket commands that only size a bracket.
_SPACES = {",": " ", ";": " ", ":": " ", " ": " ", "!": "", "quad": " ", "qquad": " "}
_DROPPED = frozenset({"left", "right", "big", "Big", "bigg", "Bigg", "displaystyle"})
# Signs and Greek letters by their command, as the glyph a student types.
_GLYPHS = {
    "times": "×",
    "cdot": "·",
    "div": "÷",
    "pm": "±",
    "mp": "∓",
    "approx": "≈",
    "sim": "~",
    "simeq": "≈",
    "leq": "≤",
    "le": "≤",
    "geq": "≥",
    "ge": "≥",
    "neq": "≠",
    "ne": "≠",
    "to": "→",
    "rightarrow": "→",
    "longrightarrow": "→",
    "infty": "∞",
    "degree": "°",
    "%": "%",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "varepsilon": "ε",
    "eta": "η",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "pi": "π",
    "rho": "ρ",
    "sigma": "σ",
    "tau": "τ",
    "phi": "φ",
    "varphi": "φ",
    "omega": "ω",
    "Delta": "Δ",
    "Omega": "Ω",
    "Phi": "Φ",
    "Sigma": "Σ",
}
# Functions written by their name: "\sin", "\ln".
_FUNCTIONS = frozenset(
    {"sin", "cos", "tan", "sec", "csc", "cot", "arcsin", "arccos", "arctan", "sinh", "cosh"}
    | {"tanh", "ln", "log", "exp"}
)
# One letter after a space, standing alone: the symbol a Greek letter is written onto.
_ONE_LETTER = re.compile(r" (?=[A-Za-z](?![A-Za-z]))")
# Marks written as a superscript: a degree sign and a prime ("f^{\prime}(x)" is f'(x)).
_MARKS = {"circ": "°", "prime": "'"}
_FRACTIONS = frozenset({"frac", "dfrac", "tfrac"})
_COMMAND = re.compile(r"\\([A-Za-z]+|.)")
_DELIMITERS = frozenset({"(", ")", "[", "]"})
# A fraction's part, or a script, that needs no brackets: "1", "m", "s^2", "v_0".
_SIMPLE = re.compile(r"[\w.°]+(?:[\^_][\w.]+)?")
# A denominator that needs no brackets: a number or one unit ("s^2", "kg", "cm^3"). Any other
# keeps its brackets: \frac{1}{4\pi\varepsilon_0} is 1/(4πε_0), never (1/4)πε_0.
_ONE_TERM = re.compile(r"\d+(?:\.\d+)?|[A-Za-z]{1,3}(?:\^-?\d+)?")
# A signed power or an ion's charge as a superscript: "s^{-2}" is s^-2, "Fe^{3+}" Fe^3+.
_CHARGE = re.compile(r"-\d+|\d*[+-]")
_FORMULA_COUNT = re.compile(r"(?<=[A-Za-z)\]])_(\d+)")
_SPACE_RUN = re.compile(r"[ \t]{2,}")
# Three digits that end a group of a number's digits: the "500" of 1\,500.
_THOUSANDS = re.compile(r"\d{3}(?![\d])")
# A run starts only where its first space is: tried from every space of a run that no mark
# follows, the run was read again from each one (quadratic).
_SPACE_BEFORE_MARK = re.compile(r"(?<![ \t])[ \t]++(?=[,.;:?!)])|(?<=\()[ \t]+")


def without_markup(text: str) -> str:
    """``text`` with its LaTeX markup written as plain text; unchanged when it has none.

    Linear in the text: each level of braces is matched once (``_pairs``), and markup past
    ``_MAX_DEPTH`` levels or a text past ``_MAX_TEXT`` is left as written, so a hostile
    paste of braces costs no more than a page of prose.
    """
    if "\\" not in text or len(text) > _MAX_TEXT:
        return text
    return _SPACE_BEFORE_MARK.sub("", _SPACE_RUN.sub(" ", _plain(text, 0))).strip()


# The longest message a subject reads at all (``symbolic_text._MAX_SUBJECT_TEXT``), and how
# deep a group may sit in another: a question's markup is two or three deep.
_MAX_TEXT = 20_000
_MAX_DEPTH = 8


def _pairs(tex: str) -> dict[int, int]:
    """Where each ``{`` that closes is closed: the index just past its ``}``."""
    pairs: dict[int, int] = {}
    opened: list[int] = []
    escaped = False
    for index, char in enumerate(tex):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "{":
            opened.append(index)
        elif char == "}" and opened:
            pairs[opened.pop()] = index + 1
    return pairs


@dataclass(frozen=True, slots=True)
class _Tex:
    """One run of markup as it is read: its text, its groups, and how deep it sits."""

    text: str
    pairs: dict[int, int]
    depth: int

    def group(self, at: int) -> tuple[str, int] | None:
        """The ``{…}`` group at ``at`` (spaces before it allowed), read plain, and its end."""
        while at < len(self.text) and self.text[at] == " ":
            at += 1
        end = self.pairs.get(at)
        return None if end is None else (_plain(self.text[at + 1 : end - 1], self.depth + 1), end)


def _plain(text: str, depth: int) -> str:
    if depth > _MAX_DEPTH:
        return text
    tex = _Tex(text, _pairs(text), depth)
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            index = _command(tex, index, out)
        elif char in "^_" and text.startswith("{", index + 1):
            index = _script(tex, index, out)
        elif char == "{" and (end := tex.pairs.get(index)) is not None:
            out.append(_plain(text[index + 1 : end - 1], depth + 1))
            index = end
        else:
            out.append(char)
            index += 1
    return "".join(out)


def _command(tex: _Tex, index: int, out: list[str]) -> int:
    """Write the command at ``index`` as plain text; return where the text goes on."""
    text = tex.text
    match = _COMMAND.match(text, index)
    if match is None:
        out.append(text[index])
        return index + 1
    name, end = match.group(1), match.end()
    if name in _DELIMITERS:
        out.append(" ")
    elif name in _SPACES:
        # A thin space between digit groups is the thousands of one number: 1\,500 is 1500.
        thousands = out and out[-1][-1:].isdigit() and _THOUSANDS.match(text, end)
        out.append("" if thousands else _SPACES[name])
    elif name in _DROPPED:
        pass
    elif name in _MARKS:
        # "30^\circ" is thirty degrees and "f^\prime" f': the caret goes with the mark.
        if out and out[-1] == "^":
            out.pop()
        out.append(_MARKS[name])
    elif name in _GLYPHS:
        out.append(_GLYPHS[name])
        # A space after a command ends its name and prints nothing: "\Delta T" is ΔT.
        if _ONE_LETTER.match(text, end):
            end += 1
    elif name in _FUNCTIONS:
        # "\sin\theta" is sin θ: the function's name stays a word of its own.
        out.append(
            name + (" " if text[end : end + 1].isalnum() or text.startswith("\\", end) else "")
        )
    elif name in _WRAPPERS and (group := tex.group(end)) is not None:
        # An upright run with a subscript count is a formula: "\\mathrm{H_2SO_4}" is H2SO4.
        out.append(_FORMULA_COUNT.sub(r"\1", group[0]))
        end = group[1]
    elif name in _FRACTIONS and (fraction := _fraction(tex, index, end, out)) is not None:
        out.append(fraction[0])
        end = fraction[1]
    elif name == "sqrt" and (root := tex.group(end)) is not None:
        out.append(f"sqrt({root[0].strip()})")
        end = root[1]
    else:
        # A command this reader does not know is the reader's own to read.
        out.append(match.group(0))
    return end


def _fraction(tex: _Tex, start: int, at: int, out: list[str]) -> tuple[str, int] | None:
    """``\\frac{a}{b}`` at ``start`` (its groups from ``at``) as a/b, and where it ends."""
    top = tex.group(at)
    if top is None:
        return None
    bottom = tex.group(top[1])
    if bottom is None:
        # No denominator: the numerator as read, never read a second time as a bare group.
        return top
    numerator, denominator = top[0].strip(), bottom[0].strip()
    shown = [
        numerator if _SIMPLE.fullmatch(numerator) else f"({numerator})",
        denominator if _ONE_TERM.fullmatch(denominator) else f"({denominator})",
    ]
    fraction = f"{shown[0]}/{shown[1]}"
    # Written against a factor, the fraction is one: "\\frac{1}{2}mv^2" is (1/2)mv^2.
    # Only what is written against it: "3 \\, \\frac{m}{s^2}" is a number and its unit.
    before = out[-1][-1:] if out else ""
    after = tex.text[bottom[1] : bottom[1] + 3].lstrip()[:2]
    # A command after it is a factor ("\\frac{1}{2}\\rho v^2"); a closing delimiter is not.
    glued = before.isalnum() or before == ")" or after[:1].isalnum() or after[:1] == "("
    glued = glued or (after[:1] == "\\" and after[1:].isalpha())
    return (f"({fraction})" if glued else fraction), bottom[1]


def _script(tex: _Tex, index: int, out: list[str]) -> int:
    """``^{2}`` is ``^2`` and ``_{1}`` is ``_1``; ``^{\\circ}`` is a degree sign."""
    group = tex.group(index + 1)
    if group is None:
        out.append(tex.text[index])
        return index + 1
    inner, end = group[0].strip(), group[1]
    mark = tex.text[index]
    if inner and set(inner) <= set(_MARKS.values()):
        out.append(inner)
    elif _SIMPLE.fullmatch(inner) or _CHARGE.fullmatch(inner):
        out.append(f"{mark}{inner}")
    else:
        out.append(f"{mark}({inner})")
    return end
