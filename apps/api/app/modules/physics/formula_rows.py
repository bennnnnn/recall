# ruff: noqa: RUF002 -- docstrings show the symbols the reader sees.
"""The law's rows on a physics reply: its base form, then each form the solver used.

The law's name is the section's heading (``law_heading``), so no row repeats it. A row
after the base is one of three things, and each reads as what it is:

- the law rearranged for the asked quantity: ``Solve for $t$`` over ``t = \\frac{d}{v}``;
- a symbol of the law worked out from the givens (ΔT from two temperatures): it is no
  unknown solved for, so it is named where the law uses it, ``with ΔT = T₂ − T₁`` over the
  law written in the givens, and its numbers belong to **Substitution**;
- the same law in the givens' terms: ``τ = F d``, with what makes it the same written
  above it (``with θ = 90°``), or nothing when it is the law rearranged on its right
  side (``P = V²/R``). A row that is the base again, spaced or braced differently, goes.
"""

from __future__ import annotations

import re

from app.modules.physics.catalog import formula_spec, select_formula
from app.modules.physics.notation import shown
from app.modules.physics.schemas import PhysicsIntent
from app.services.law_binding.inverse import form_params
from app.services.workout import math_line, solve_for_line, text_line

# A script of one character with or without braces (v^{2}, v^2), and a function of one
# argument with or without brackets (\sin(\theta), \sin\theta; \arcsin(\frac{1}{n}),
# \arcsin\frac{1}{n}), print the same law.
_BRACED_SCRIPT = re.compile(r"([_^])\{(\\[A-Za-z]+|[A-Za-z0-9])\}")
_FUNCTION_BRACKET = re.compile(r"\\(?:arcsin|arccos|arctan|sin|cos|tan|ln|log)\(")
_ONE_ARGUMENT = re.compile(r"\\?[A-Za-z]+(?:_[A-Za-z0-9])?|\\(?:frac|sqrt)(?:\{[^{}]*\})+")
# Spellings that print the same: a text-size fraction, sized brackets.
_SAME_PRINT = (
    (r"\tfrac", r"\frac"),
    (r"\dfrac", r"\frac"),
    (r"\left", ""),
    (r"\right", ""),
    (r"\cdot", ""),
    (r"\times", ""),
    (r"\,", ""),
    (" ", ""),
)
# One symbol: a letter, a Greek command or a command with its braced argument (\mathcal{E},
# \bar{v}, \dot{m}); a Δ before it; a subscript after it, which may hold a command of its
# own (t_{\text{top}}, v_{\mathrm{rms}}, B_\lambda).
_SYMBOL = re.compile(
    r"(?:\\Delta\s*)?(?:\\[A-Za-z]+(?:\{[^{}]+\})?|[A-Za-z])"
    r"(?:_\{(?:[^{}]|\{[^{}]*\})+\}|_\\[A-Za-z]+|_[A-Za-z0-9])?'?"
)
# The angle a law multiplies by its sine, and the one it multiplies by its cosine.
_SINE = re.compile(r"\\sin\s*\(?\s*\\theta\s*\)?")
_COSINE = re.compile(r"\\cos\s*\(?\s*\\theta\s*\)?")


def _unbracket_functions(text: str) -> str:
    """Drop the brackets round a function's argument when the argument is one atom."""
    out: list[str] = []
    cursor = 0
    for match in _FUNCTION_BRACKET.finditer(text):
        if match.start() < cursor:
            continue
        depth, close = 1, match.end()
        while close < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[close], 0)
            close += 1
        inner = text[match.end() : close - 1]
        if depth == 0 and _ONE_ARGUMENT.fullmatch(inner):
            out.append(text[cursor : match.end() - 1] + inner)
            cursor = close
    return "".join(out) + text[cursor:]


def formula_identity(formula: str) -> str:
    """Ignore presentation-only differences when comparing laws: spacing,
    multiplication dots, braces round a one-character script, brackets round a
    one-atom argument. Torque and centripetal force were each listed twice."""
    text = formula
    for spelling, same in _SAME_PRINT:
        text = text.replace(spelling, same)
    return _unbracket_functions(_BRACED_SCRIPT.sub(r"\1\2", text))


def _sides(formula: str) -> list[str]:
    return [side.strip() for side in formula.split(" = ")]


def _is_symbol(text: str) -> bool:
    return _SYMBOL.fullmatch(text.strip().strip("|")) is not None


def _uses(formula: str, symbol: str) -> bool:
    """Whether ``symbol`` appears in ``formula`` as itself, not inside a longer name."""
    return re.search(rf"{re.escape(symbol)}(?![A-Za-z_{{])", formula) is not None


def _definition(formula: str, base: str, asked: str | None) -> tuple[str, str] | None:
    """(symbol, what it is) when ``formula`` works out a symbol of the base law from the
    givens (``ΔT = T_2 - T_1 = 80 - 20 = 60``), not the asked quantity rearranged."""
    sides = _sides(formula)
    symbol = sides[0]
    if len(sides) < 2 or not _is_symbol(symbol) or symbol == asked:
        return None
    base_right = " = ".join(_sides(base)[1:])
    if not _uses(base_right, symbol):
        return None
    return symbol, sides[1]


def _why_same(formula: str, base: str, definitions: list[tuple[str, str]]) -> str | None:
    """What turns the base law into ``formula``, as a note above it: a symbol the law
    defines from the givens written out (``with ΔT = T₂ − T₁``), or the right angle a
    sine of θ drops at (``with θ = 90°``). None when it is neither."""
    target = formula_identity(formula)
    for symbol, meaning in definitions:
        if formula_identity(base.replace(symbol, f"({meaning})")) == target:
            return f"with ${symbol} = {meaning}$"
    if formula_identity(_SINE.sub("", base)) == target:
        return r"with $\theta = 90^\circ$"
    if formula_identity(_COSINE.sub("", base)) == target:
        return r"with $\theta = 0^\circ$"
    return None


def formula_rows(
    intent: PhysicsIntent,
    formulas: list[str],
    asked: str | None,
    operation: str | None = None,
) -> list[str]:
    """The governing law's base form, then each form the solver used (module docstring).
    ``asked`` is the symbol **Required** names; ``operation`` is one part's, in a question
    in parts."""
    operation = operation or intent.physics_op or ""
    spec = formula_spec(operation)
    params = intent.physics_params or {}
    base: str | None = None
    lines: tuple[str, ...] = ()
    if spec is not None:
        base, lines, _assumptions = select_formula(spec, form_params(spec, params))
        base = None if base is None else shown(base, operation)
        lines = tuple(shown(line, operation) for line in lines)
    if lines:
        return [math_line(line) for line in lines]
    if base is None:
        return [math_line(formula) for formula in formulas]

    rows = [math_line(base)]
    base_lhs = base.split(" = ", 1)[0].strip()
    # Every side of a chained base (``v_{max} = A\omega = A\sqrt{\frac{k}{m}}``) is the law.
    stated = {formula_identity(side) for side in _sides(base)[1:]}
    definitions: list[tuple[str, str]] = []
    pending: list[str] = []
    for formula in formulas:
        formula_lhs = formula.split(" = ", 1)[0].strip()
        if formula_identity(formula) == formula_identity(base):
            continue
        if formula_lhs == base_lhs:
            if formula_identity(" = ".join(_sides(formula)[1:])) in stated:
                continue
            why = _why_same(formula, base, definitions)
            # A definition written out on this row is its note, not a line of its own.
            pending = [line for line in pending if why is None or line != _where(why)]
            rows.extend(pending)
            pending = []
            rows.append(math_line(formula, why))
            continue
        defined = _definition(formula, base, asked)
        if defined is not None:
            definitions.append(defined)
            pending.append(_where(f"with ${defined[0]} = {defined[1]}$"))
        elif formula_lhs != asked and not _is_symbol(formula_lhs):
            # A balance (``0 = m_1 v_1 - m_2 v_2``) states the law; nothing is solved for.
            # The asked quantity is solved for whatever its shape (MA, N/N₀).
            rows.append(math_line(formula))
        else:
            rows.extend((solve_for_line(formula_lhs), math_line(formula)))
    rows.extend(pending)
    return rows


def _where(with_note: str) -> str:
    """``with $X = …$`` as a line of its own: ``where $X = …$``."""
    return text_line(f"where {with_note.removeprefix('with ')}")
