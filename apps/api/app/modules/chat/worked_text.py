# ruff: noqa: RUF001, RUF002, RUF003 -- Greek letters and maths signs are read as written.
r"""The model's words and symbols in a ```worked block, as the layout shows them.

A block's maths fields hold LaTeX; its other fields hold words: a formula's heading, a
move, what a given or an unknown is, a part's title, a note after the answer. A model
writes maths into the words too ("Substitution x = \tan t", DeepSeek, 2026-11-11), and
words reach the phone as text, so those showed as LaTeX source. Every word field goes
through ``worked_prose.prose_maths``, which marks its maths as inline maths; the phone
draws ``$…$`` as maths in a heading, a note and a line alike (``rules/workout.tsx``).

A maths field is written one way (``tidy_tex``): a Greek letter as its command, as the
model's own formulas write it, so the unknown under Required (``ρ``) and in the working
(``\rho``) is one symbol, never two spellings drawn in two fonts (2026-11-11). So is a word
symbol: ``\text{white\_pigment}`` in the working is the ``white_{pigment}`` its Required
line writes, never the escaped underscore shown as source (2026-11-12). A unit the given
and answer records name is set upright after a number in the working, as their own lines
set it (``units_in_working``).
"""

from __future__ import annotations

import re
import unicodedata

from app.modules.chat.worked_prose import prose_maths
from app.modules.chat.worked_solution import Formula, Step, WorkedSolution
from app.modules.chat.worked_units import (
    WORD_GROUP,
    currency_first,
    declared_units,
    units_upright,
)
from app.services.latex_groups import closed_group_end, map_groups
from app.services.times_sign import with_times
from app.services.workout import formula_heading

_BOLD = re.compile(r"\*\*(.+?)\*\*")
# An escaped underscore (``\_``) is a character, never a script: ``\_pigment`` stays whole.
_LONG_SUBSCRIPT = re.compile(r"(?<!\\)_(?![{\\])([A-Za-z0-9]{2,})")
_NUMBERED = re.compile(r"^([A-Za-z])(\d+)$")
# LaTeX syntax or a relation: a field holding any of them is maths.
_MATH_SYNTAX = re.compile(r"[\\{}^_=<>≤≥≈≠]")
_WORDS = re.compile(r"[^\W\d_]{2,}")

# The Greek capitals LaTeX has a command for; the others are written as Latin letters.
_CAPITALS = frozenset(
    {"Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega"}
)
_GREEK_LETTER = re.compile(r"GREEK (SMALL|CAPITAL) LETTER ([A-Z]+)")


def _greek_command(char: str) -> str | None:
    named = _GREEK_LETTER.fullmatch(unicodedata.name(char, ""))
    if named is None:
        return None
    # Unicode spells lambda "LAMDA"; omicron has no command.
    word = named.group(2).lower().replace("lamda", "lambda")
    if named.group(1) == "CAPITAL":
        return word.capitalize() if word.capitalize() in _CAPITALS else None
    return None if word == "omicron" else word


_GREEK = {
    char: command
    for char in map(chr, range(0x391, 0x3CA))
    if (command := _greek_command(char)) is not None
}
# The micro sign a keyboard types for μ.
_GREEK["\u00b5"] = "mu"
# A group whose letters are set upright, a unit's ``\mathrm{μC}``: its letters are text.
_UPRIGHT_OPEN = re.compile(r"\\(?:mathrm|textrm|text|operatorname|mbox)\s*\{")


def _group_end(text: str, opening: int) -> int:
    """Where the brace group opened at ``opening`` ends (past its ``}``), or the text's end."""
    depth = 0
    for at in range(opening, len(text)):
        if text[at] == "{":
            depth += 1
        elif text[at] == "}":
            depth -= 1
            if depth == 0:
                return at + 1
    return len(text)


def greek_as_commands(tex: str) -> str:
    """``ρ = \\frac{m}{V}`` → ``\\rho = \\frac{m}{V}``: each Greek letter in maths as its
    command, a unit's letters (``\\mathrm{μC}``) left as written."""
    if not any(char in _GREEK for char in tex):
        return tex
    out: list[str] = []
    at = 0
    while at < len(tex):
        upright = _UPRIGHT_OPEN.match(tex, at)
        if upright is not None:
            end = _group_end(tex, upright.end() - 1)
            out.append(tex[at:end])
            at = end
            continue
        command = _GREEK.get(tex[at])
        if command is None:
            out.append(tex[at])
        else:
            # "ρV" is ρ times V: the command ends before a letter.
            out.append(f"\\{command}{' ' if tex[at + 1 : at + 2].isalpha() else ''}")
        at += 1
    return "".join(out)


# An underscore a model escaped for text mode, between a name and its subscript: in a word
# group (``\text{white\_pigment}``) or bare (``white\_pigment``).
_ESCAPED_SCRIPT = re.compile(r"(?<=[A-Za-z0-9])\\_(?=[{A-Za-z0-9])")
_BARE_ESCAPED_SCRIPT = re.compile(r"(?<=[A-Za-z0-9}])\\_(?=[{A-Za-z0-9])")
_SCRIPT_WORDS = re.compile(r"[A-Za-z0-9]+(?:\\_[A-Za-z0-9]+)*")
_NAMED = re.compile(
    r"(?P<base>[A-Za-z][A-Za-z0-9]*)\\_(?:\{(?P<braced>[A-Za-z0-9]+)\}|(?P<bare>[A-Za-z0-9]+))"
)


def _scripted_group(command: str, content: str) -> str:
    """A word group's content with each escaped underscore as the subscript it stands
    for. A name and its subscript alone (``white\\_pigment``, ``white\\_{pigment}``) is the
    symbol the symbol fields write, ``white_{pigment}``: one symbol, one spelling in every
    line. Words around it stay upright words (``cost\\_per item`` → ``\\text{cost}`` with the
    subscript ``\\text{per}``, then ``\\text{ item}``), and several joined words after it are
    the subscript's words (``mass\\_of\\_salt`` → mass, subscript "of salt")."""
    named = _NAMED.fullmatch(content.strip())
    if named is not None:
        return f"{named['base']}_{{{named['braced'] or named['bare']}}}"
    found = _ESCAPED_SCRIPT.search(content)
    if found is None:
        return rf"\{command}{{{content}}}"
    after = content[found.end() :]
    words = _SCRIPT_WORDS.match(after)
    if (end := closed_group_end(after, 0)) is not None:
        script, rest = after[1 : end - 1], after[end:]
    elif words is not None:
        script, rest = words.group(0), after[words.end() :]
    else:
        return rf"\{command}{{{content}}}"  # a brace never closed: as written
    script = script.replace("\\_", " ").strip()
    tail = _scripted_group(command, rest) if rest else ""
    before = rf"\{command}{{{content[: found.start()]}}}"
    return rf"{before}_{{\{command}{{{script}}}}}{tail}"


def word_scripts(tex: str) -> str:
    r"""A word symbol's subscript as a subscript. A model escapes the underscore that joins
    a name and its subscript, as text mode needs (``\text{white\_pigment}``), and read as
    written the phone drew the underscore and the brace the layout put after it
    ("white_{pigment}", 2026-11-12). The name is the symbol its Given, Required and Answer
    lines write from the symbol fields (``white_{pigment}``), in a word group or bare in
    maths (``_scripted_group``). An escaped underscore before anything but a word or a
    brace (a blank, ``\_\_``) is the character it is."""
    return map_groups(
        tex,
        WORD_GROUP,
        lambda maths: _BARE_ESCAPED_SCRIPT.sub("_", maths),
        lambda opened, text: _scripted_group(opened["command"], text),
    )


def tidy_tex(tex: str) -> str:
    """A subscript of several characters in braces: ``x_final`` → ``x_{final}``; a word
    symbol's escaped subscript as a subscript (``word_scripts``); a product written with
    a dot, with \\times as every reply writes it (``services/times_sign``). Markdown bold
    a model put in a maths field (``**1.2**``) is dropped: TeX has none. A currency sign
    after a number goes before it (``worked_units``), and a Greek letter is its command."""
    tex = word_scripts(_BOLD.sub(r"\1", tex.strip()))
    return greek_as_commands(currency_first(with_times(_LONG_SUBSCRIPT.sub(r"_{\1}", tex))))


def tidy_symbol(symbol: str) -> str:
    """``m1`` → ``m_1``: a letter numbered by the digits after it, as a subscript."""
    return tidy_tex(_NUMBERED.sub(r"\1_\2", symbol.strip()))


def is_prose(field: str) -> bool:
    """Words the model put in a maths field ("Let A be the origin"), told by structure:
    no LaTeX syntax and no relation, and a word of two letters or more. Anything with a
    backslash, brace, script or relation is maths, so no LaTeX source is ever shown."""
    return _MATH_SYNTAX.search(field) is None and _WORDS.search(field) is not None


def names_nothing(symbol: str) -> bool:
    """A "symbol" written in words ("length in cm", "a) in cm")."""
    return " " in symbol.strip() and is_prose(symbol)


# Where a heading's own words end and a remark on them starts: a bracket, a colon, a
# semicolon, a dash or a comma, outside maths.
_REMARK = re.compile(r"\s*(?:[(:;—–]|,\s| - )")


def formula_title(name: str) -> str:
    """The heading over the model's formula, by the one rule every subject heads a formula
    with (``services.workout.formula_heading``: "Average speed" reads Average speed
    formula, "Ohm's law" stays), its maths drawn as maths ("Substitution $x = \\tan t$").
    A name too long to read as a heading keeps its words up to a remark ("Conservation of
    energy (the potential energy …)"). None is "": the formula follows **Solution** with
    no heading of its own, never under a bare **Formula** (2026-11-11)."""
    title = prose_maths(name)
    return formula_heading(title) or formula_heading(_before_remark(title))


def _before_remark(title: str) -> str:
    in_maths = False
    for at, char in enumerate(title):
        if char == "$":
            in_maths = not in_maths
        elif not in_maths and _REMARK.match(title, at) and at > 0:
            return title[:at]
    return title


def units_in_working(solution: WorkedSolution) -> WorkedSolution:
    """The solution with each unit its given and answer records name set upright after a
    number in its working (``worked_units.units_upright``), as those records' own lines
    set it: ``W = 12 gal`` reads as the card's ``12\\,\\mathrm{gal}``. A line of words is
    left as words."""
    givens = [*solution.given, *(given for part in solution.parts for given in part.given)]
    answers = [answer for part in solution.parts for answer in part.answers]
    units = declared_units(
        [*(given.unit for given in givens), *(answer.unit for answer in answers)]
    )
    if not units:
        return solution

    def upright[Line: (Step, Formula)](line: Line) -> Line:
        if is_prose(line.tex):
            return line
        return line.model_copy(update={"tex": units_upright(line.tex, units)})

    parts = tuple(
        part.model_copy(
            update={
                "formula": part.formula and upright(part.formula),
                "working": tuple(upright(step) for step in part.working),
            }
        )
        for part in solution.parts
    )
    return solution.model_copy(update={"parts": parts})
