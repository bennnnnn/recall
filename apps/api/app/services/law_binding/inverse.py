"""A law solved for any one of its quantities, from its result and the rest.

A catalog law writes its result as arithmetic in its inputs (W = Fs, density = m/V). A
question may state the result and ask for an input instead: "an engine does 400 J of work
with a force of 80 N: how far does the cart move?" asks s = W/F, and "a liquid of density
2.5 g/mL: what is the mass of 40 mL?" asks the density times the volume. Each such question
was left to the model (phone test, 2026-11-11), though the law it needs was in the catalog.

So every law written as arithmetic is solved for whichever of its inputs is asked:

- ``solved_for`` is the law as the binder fills it for that input: the law's result is one
  of its inputs (``spec.result_variable``) and the asked input is its result. It keeps the
  law's id, so the reply names the law, its symbols and its picture as before;
- ``rearranged`` is the arithmetic for that input, which SymPy works out from the law's own
  expression: one solution, in the grammar ``expression`` evaluates, or none. Every one a
  catalog law can ask is worked out ahead and kept as data (``rearrangements``); SymPy
  works out any other in the pool with the turn's readers (Golden Rule 7);
- ``solved_input`` reads, from an intent's values, which input a solve is for.

The law is named by its result stated in its own words (``stated_strength``), and a
direction another law of the catalog owns is left to that law (``answered_by_its_own_law``).
The solver puts each answer back into the law and refuses one that does not give the
stated result, so a rearrangement's branch never answers for values it does not hold for.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Mapping
from dataclasses import replace
from functools import lru_cache
from itertools import pairwise
from typing import Any

from app.services.law_binding.expression import ExpressionError, parse
from app.services.law_binding.fit import Question, given_kind, value_end, variable_kind
from app.services.law_binding.rearrangements import kept_rearrangements, kept_sizes
from app.services.law_binding.roles import result_role, role_words
from app.services.law_binding.spec import (
    Binding,
    FormulaSpec,
    VariableSpec,
    matching_variant,
    result_variable,
)
from app.services.law_binding.units import UnitTable, dimension_of
from app.services.law_binding.words import words_after, words_before


def solved_input(spec: FormulaSpec, params: Mapping[str, float]) -> VariableSpec | None:
    """The input this solve is for: the law's result is stated and that input is not.

    None for a law solved for its own result, the usual way.
    """
    result = result_variable(spec)
    binding = spec.binding
    if result is None or binding is None or result.name not in params:
        return None
    stated = set(params) - {result.name}
    missing = [
        variable
        for variable in spec.variables
        if variable.visible
        and variable.name not in stated
        and frozenset({*stated, variable.name}) in binding.inputs
    ]
    return missing[0] if len(missing) == 1 else None


@lru_cache(maxsize=1024)
def stated_result(spec: FormulaSpec) -> VariableSpec | None:
    """The law's result as a question states it, named by its words (``result_variable``).

    A result at one end of a change (Boyle's P₂, "the new pressure") is named only by the
    words for that end: "its initial pressure was 100 kPa" states P₁, never P₂.
    """
    result = result_variable(spec)
    if result is None or spec.binding is None or result_role(spec.binding) is None:
        return result
    return replace(result, words=role_words(spec.binding.asks))


def form_params(spec: FormulaSpec, params: Mapping[str, float]) -> dict[str, float]:
    """The values that choose the law's form (``spec.variants``): the givens, and the input
    a law given its result is solved for, which its form holds. P = W/t solved for W is
    still the law P = W/t, though W is not given."""
    unknown = solved_input(spec, params)
    return dict(params) if unknown is None else {**params, unknown.name: 1.0}


@lru_cache(maxsize=1024)
def solved_for(spec: FormulaSpec, name: str) -> FormulaSpec | None:
    """The law as it is filled to find its input ``name``, or None when it cannot be.

    Its inputs are the law's others and its own result, in every set the law answers from
    that holds ``name``. A form of the law chosen by a condition on ``name`` itself (its
    sign, its value) cannot be chosen before ``name`` is known, so that law is not solved
    for it.
    """
    result = stated_result(spec)
    binding = spec.binding
    unknown = next((v for v in spec.variables if v.name == name and v.visible), None)
    if result is None or binding is None or unknown is None:
        return None
    if any(name in variant.positive or name in dict(variant.equals) for variant in spec.variants):
        return None
    inputs = tuple(
        frozenset({*(inputs - {name}), result.name}) for inputs in binding.inputs if name in inputs
    )
    if not inputs:
        return None
    return replace(
        spec,
        result_symbol=unknown.symbol,
        # The stated result takes only a value its words name: no other value is the law's.
        variables=(
            *(v for v in spec.variables if v.name != name),
            replace(result, needs_words=True),
        ),
        # The rearrangement is the solver's, once the law's form is chosen from the givens.
        variants=(),
        solve_for=(),
        expression=None,
        binding=Binding(
            # The asked input names no ask of its own: the law is named by its result,
            # stated ("400 J of work"), and the asked quantity is read by its kind.
            asks=(),
            result=(unknown.dimension or "dimensionless",),
            inputs=inputs,
            cues=binding.cues,
            excludes=binding.excludes,
            descending=tuple(other for other in binding.descending if other != name),
            interchangeable=tuple(other for other in binding.interchangeable if other != name),
            nonnegative=True,
        ),
    )


def stated_strength(stated: VariableSpec, question: Question, units: UnitTable) -> int:
    """How strongly the question states a law's result: the longest of the words the law is
    asked with (``stated.words``) that label a value of its kind, 0 when none does.

    A label comes just before the value, at most a few words away and joined to it by "of",
    "is" or "=" ("a density of 2.5 g/mL", "the work done on the cart is 400 J"), or just
    after it ("400 J of work"). A word of the law elsewhere in the sentence labels nothing:
    "rises in a capillary tube of diameter 1 mm" states a diameter, not the rise.
    """
    lower, givens = question.lower, question.givens
    kind = variable_kind(stated)
    strength = 0
    for index, given in enumerate(givens):
        if given_kind(given, units) != kind:
            continue
        following = givens[index + 1].start if index + 1 < len(givens) else len(lower)
        before = words_before(lower, 0, given.start)
        after = words_after(lower, value_end(lower, given), following)
        for phrase in stated.words:
            before_label, after_label = _labels(phrase)
            if before_label.search(before) or after_label.match(after):
                strength = max(strength, len(phrase))
    return strength


@lru_cache(maxsize=512)
def _labels(phrase: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    """The phrase as a label written before a value, and as one written after it."""
    words = re.escape(phrase)
    before = re.compile(
        rf"(?<![\w]){words}(?:\s+[^\s\d.,;:?!=]+){{0,6}}?\s*"
        r"(?:of|is|was|are|were|equals?|equal\s+to|=|:|≈)\s*"
        r"(?:about\s+|approximately\s+|roughly\s+)?$"
    )
    after = re.compile(rf"\s*(?:of\s+)?(?:the\s+)?{words}(?![\w])")
    return before, after


def answered_by_its_own_law(
    spec: FormulaSpec, variable: VariableSpec, laws: Iterable[FormulaSpec]
) -> bool:
    """Another law of the catalog relates the same quantities and gives ``variable``'s kind
    as its result: that law answers the question, with its own checks, or nothing does.

    m = F/a solved for F is F = ma, which the catalog has (``net_force``), read with what
    sets it aside ("a spring", "centripetal"). Solved here instead, "how much force does a
    spring exert on a 5 kg mass accelerating at 2 m/s²" was F = ma = 10 N.
    """
    quantities = _quantity_kinds(spec)
    kind = variable_kind(variable)
    for law in laws:
        if law.id == spec.id or law.kind != spec.kind or _quantity_kinds(law) != quantities:
            continue
        gives = {dimension_of(unit) for unit in law.binding.result} if law.binding else set()
        solves = {
            variable_kind(other)
            for other in law.variables
            if other.name in {name for name, _symbol in law.solve_for}
        }
        if kind in gives or kind in solves:
            return True
    return False


@lru_cache(maxsize=1024)
def _quantity_kinds(spec: FormulaSpec) -> tuple[str, ...]:
    """The kinds of every quantity a law relates, its result among them, in order."""
    kinds = [variable_kind(variable) for variable in spec.variables if variable.visible]
    if not spec.solve_for and spec.binding is not None:
        kinds.extend(dimension_of(unit) for unit in spec.binding.result)
    return tuple(sorted(kind or "" for kind in kinds))


def twins(spec: FormulaSpec) -> frozenset[str]:
    """Inputs that play the same part: interchangeable, of one kind, and the law the same
    with any two swapped (F = m(u + v)/t in its two speeds), so solving for either is one
    unknown. Two skaters' masses, filled in order, are not: m₁v₁ = m₂v₂ pairs each with
    its own speed."""
    binding = spec.binding
    names = frozenset(binding.interchangeable) if binding is not None else frozenset()
    kinds = {variable_kind(v) for v in spec.variables if v.name in names}
    if len(kinds) != 1 or spec.expression is None or not _symmetric(spec.expression, names):
        return frozenset()
    return names


def same_part(spec: FormulaSpec) -> frozenset[str]:
    """The like parts a law combines into a whole of their own kind (P = P₁ + P₂, two
    capacitors' C): its twins, of the result's kind. Two currents giving a force per metre
    are no parts of a whole."""
    parts = twins(spec)
    binding = spec.binding
    if not parts or binding is None:
        return frozenset()
    kinds = {variable_kind(v) for v in spec.variables if v.name in parts}
    return parts if kinds <= {dimension_of(unit) for unit in binding.result} else frozenset()


@lru_cache(maxsize=256)
def _symmetric(expression: str, names: frozenset[str]) -> bool:
    """The arithmetic is unchanged by swapping any two of ``names``."""
    import sympy

    symbols: dict[str, Any] = {}

    def symbol(name: str) -> Any:
        if name not in symbols:
            symbols[name] = sympy.Symbol(name, positive=True)
        return symbols[name]

    try:
        law = _to_sympy(parse(expression), symbol)
    except (ExpressionError, ValueError):
        return False
    ordered = sorted(names)
    for first, second in pairwise(ordered):
        swapped = law.subs(
            {symbol(first): symbol(second), symbol(second): symbol(first)}, simultaneous=True
        )
        if sympy.simplify(law - swapped) != 0:
            return False
    return True


def can_solve_for(spec: FormulaSpec, name: str) -> bool:
    """Whether some form of the law that holds ``name`` is solved for it (``inverse_of``):
    P = W/t for W, though the law's first form, P = Fv, has no W."""
    if spec.binding is None:
        return False
    for inputs in spec.binding.inputs:
        forward = forward_expression(spec, dict.fromkeys(inputs, 1.0)) if name in inputs else None
        if forward is not None and inverse_of(spec, forward, name) is not None:
            return True
    return False


def inverse_of(spec: FormulaSpec, forward: str, name: str) -> str | None:
    """The law's form ``forward`` solved for ``name`` (``rearranged``), when the answer does
    not hang on a sign the question's words leave out; else None.

    A question states a result as a size: "gives out 36000 J of heat", "3000 J of work is
    done on the gas", "a 40 N force in the opposite direction". A law whose result has a
    sign is answered only when that sign changes the answer's sign alone, never its size:
    s = W/F is 5 m however W is signed. T₂ = T₁ + Q/mc is not: read as +36000 J, an iron
    block cooling from 80 °C ended at 120 °C. A law that prints its result as a size with
    a note (``negative_detail``: "releases", "opposing the motion") is never solved so.
    """
    stated = result_variable(spec)
    binding = spec.binding
    if stated is None or binding is None or binding.negative_detail:
        return None
    inverse = rearranged(forward, stated.name, name)
    if inverse is None or not (binding.nonnegative or keeps_its_size(inverse, stated.name)):
        return None
    return inverse


def forward_expression(spec: FormulaSpec, params: Mapping[str, float]) -> str | None:
    """The arithmetic of the law's result for these inputs: the form its givens choose."""
    variant = matching_variant(spec, dict(params))
    if variant is not None and variant.expression is not None:
        return variant.expression
    return spec.expression


# What SymPy may print that the expression grammar spells otherwise.
_SYMPY_NAMES = (("Abs(", "abs("),)
# A placeholder no catalog name can be: SymPy works on its own copy of each name.
_PLACEHOLDER = re.compile(r"^_?[A-Za-z][A-Za-z0-9_]*$")


@lru_cache(maxsize=1024)
def rearranged(expression: str, result: str, unknown: str) -> str | None:
    """``result = expression`` solved for ``unknown``, as an expression in the same names.

    None unless SymPy finds exactly one solution in the grammar ``expression`` evaluates
    (``parse``). Every name is taken as positive, as a measured size is: v = sqrt(2E/m),
    never its negative twin. A value that is not positive is the solver's to refuse, when
    the answer put back into the law does not give the stated result.

    A catalog law's is read from the kept table, which holds SymPy's own answer: solving
    took 0.3 s for most laws and 1.4 s for an angle on an incline, inside a turn's read.
    """
    kept = kept_rearrangements()
    key = (expression, result, unknown)
    return kept[key] if key in kept else sympy_rearranged(expression, result, unknown)


def sympy_rearranged(expression: str, result: str, unknown: str) -> str | None:
    """``rearranged`` as SymPy works it out, for an expression the kept table lacks."""
    import sympy

    if not all(_PLACEHOLDER.match(name) for name in (result, unknown)):
        return None
    names: dict[str, Any] = {}

    def symbol(name: str) -> Any:
        if name not in names:
            names[name] = sympy.Symbol(name, positive=True)
        return names[name]

    try:
        law = _to_sympy(parse(expression), symbol)
    except (ExpressionError, ValueError):
        return None
    if unknown not in names:
        return None
    try:
        solutions = sympy.solve(sympy.Eq(symbol(result), law), symbol(unknown))
    except (NotImplementedError, ValueError, TypeError):
        return None
    if len(solutions) != 1 or solutions[0].has(sympy.I):
        return None
    text = str(solutions[0])
    for written, spelled in _SYMPY_NAMES:
        text = text.replace(written, spelled)
    try:
        parse(text)
    except ExpressionError:
        return None
    return text


@lru_cache(maxsize=1024)
def keeps_its_size(inverse: str, result: str) -> bool:
    """The answer ``inverse`` gives has the same size whichever sign ``result`` has.

    A catalog law's answer is read from the kept table, as ``rearranged``'s is.
    """
    kept = kept_sizes()
    key = (inverse, result)
    return kept[key] if key in kept else sympy_keeps_its_size(inverse, result)


def sympy_keeps_its_size(inverse: str, result: str) -> bool:
    """``keeps_its_size`` as SymPy works it out."""
    import sympy

    names: dict[str, Any] = {}

    def symbol(name: str) -> Any:
        if name not in names:
            names[name] = sympy.Symbol(name, positive=True)
        return names[name]

    try:
        answer = _to_sympy(parse(inverse), symbol)
    except (ExpressionError, ValueError):
        return False
    stated = symbol(result)
    try:
        return bool(sympy.simplify(answer.subs(stated, -stated) ** 2 - answer**2) == 0)
    except (TypeError, ValueError):
        return False


def _to_sympy(node: ast.expr, symbol: Any) -> Any:
    """The checked tree of a catalog expression as a SymPy expression."""
    import sympy

    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return sympy.Rational(str(node.value))
    if isinstance(node, ast.Name):
        return symbol(node.id)
    if isinstance(node, ast.UnaryOp):
        operand = _to_sympy(node.operand, symbol)
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function = sympy.Abs if node.func.id == "abs" else getattr(sympy, node.func.id)
        return function(_to_sympy(node.args[0], symbol))
    if isinstance(node, ast.BinOp):
        left, right = _to_sympy(node.left, symbol), _to_sympy(node.right, symbol)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
    # A condition chooses between two forms of a law; neither is the law to rearrange.
    raise ValueError(f"cannot rearrange {type(node).__name__}")
