"""Verified inverse-operation traces for linear, pure-power, and quadratic equations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sympy import (
    Abs,
    Eq,
    Poly,
    Symbol,
    expand,
    factor,
    latex,
    simplify,
    solve,
    sqrt,
)


@dataclass(frozen=True)
class KeyStep:
    """One justified transformation. Formula is LaTeX without ``$`` wrappers."""

    label: str
    formula: str
    reason: str | None = None
    conditions: str | None = None
    branch: str | None = None


def stringify_key_steps(steps: list[KeyStep]) -> list[str]:
    return [f"{step.label}: {step.formula}" for step in steps]


def equation_key_steps(lhs: Any, rhs: Any, variable: str) -> list[KeyStep]:
    """Structured working from the original sides. Empty when the shape is unsupported."""
    var = Symbol(variable)
    rational_steps = _rational_equation_key_steps(lhs, rhs, var)
    if rational_steps is not None:
        return rational_steps
    try:
        poly = Poly(simplify(lhs - rhs), var)
        degree = poly.degree()
    except Exception:
        return []
    if degree == 1:
        return _linear_key_steps(lhs, rhs, var, poly)
    if degree == 2:
        return _quadratic_key_steps(lhs, rhs, var, poly)
    return []


def _rational_equation_key_steps(lhs: Any, rhs: Any, var: Any) -> list[KeyStep] | None:
    left_num, left_den = getattr(lhs, "as_numer_denom", lambda: (lhs, 1))()
    right_num, right_den = getattr(rhs, "as_numer_denom", lambda: (rhs, 1))()
    left_has_variable_denominator = var in getattr(left_den, "free_symbols", set())
    right_has_variable_denominator = var in getattr(right_den, "free_symbols", set())
    if left_has_variable_denominator == right_has_variable_denominator:
        return None
    try:
        if left_has_variable_denominator:
            cleared_lhs = left_num
            cleared_rhs = simplify(rhs * left_den)
            denominator = left_den
            multiplied = f"{latex(left_num)} = {latex(rhs)} \\left({latex(left_den)}\\right)"
        else:
            cleared_lhs = simplify(lhs * right_den)
            cleared_rhs = right_num
            denominator = right_den
            multiplied = f"{latex(lhs)} \\left({latex(right_den)}\\right) = {latex(right_num)}"
        poly = Poly(simplify(cleared_lhs - cleared_rhs), var)
        if poly.degree() != 1:
            return []
        excluded = solve(Eq(denominator, 0), var)
        solutions = [
            solution
            for solution in solve(Eq(lhs, rhs), var)
            if all(not _expr_equal(solution, value) for value in excluded)
        ]
    except Exception:
        return []
    if not solutions:
        return []
    condition = ""
    if excluded:
        exclusions = r",\; ".join(rf"{latex(var)} \ne {latex(value)}" for value in excluded)
        condition = rf", \quad {exclusions}"
    steps = [
        KeyStep(
            label=f"Multiply both sides by {latex(denominator)}",
            formula=f"{multiplied}{condition}",
        )
    ]
    steps.append(KeyStep(label="Expand", formula=_eq_tex(cleared_lhs, cleared_rhs)))
    linear_steps = _linear_key_steps(cleared_lhs, cleared_rhs, var, poly)
    index = 0
    while index < len(linear_steps):
        step = linear_steps[index]
        if index + 1 < len(linear_steps) and linear_steps[index + 1].label == "Simplify":
            step = KeyStep(
                label=step.label,
                formula=linear_steps[index + 1].formula,
                reason=step.reason,
                conditions=step.conditions,
                branch=step.branch,
            )
            index += 1
        steps.append(step)
        index += 1
    final = r" \text{ or } ".join(f"{latex(var)} = {latex(solution)}" for solution in solutions)
    if steps[-1].label.startswith(("Divide both sides", "Multiply both sides")):
        steps[-1] = KeyStep(label=steps[-1].label, formula=final, reason=steps[-1].reason)
    else:
        steps.append(KeyStep(label="Simplify", formula=final))
    return steps


def equation_check_latex(lhs: Any, rhs: Any, variable: str) -> str | None:
    """Short substitution check when every root is rational."""
    try:
        var = Symbol(variable)
        solutions = solve(Eq(lhs, rhs), var)
    except Exception:
        return None
    if not solutions:
        return None
    try:
        if not all(getattr(sol, "is_number", False) and bool(sol.is_rational) for sol in solutions):
            return None
    except Exception:
        return None
    if len(solutions) == 2 and _expr_equal(solutions[0] + solutions[1], 0):
        pos = simplify(Abs(solutions[0]))
        dummy = Symbol("QQQ")
        left = latex(lhs.subs(var, dummy)).replace("QQQ", rf"(\pm {latex(pos)})")
        return f"{left} = {latex(rhs)}"
    parts = [_substituted_eq(lhs, rhs, var, sol) for sol in solutions]
    if not all(parts):
        return None
    return r" \text{ and } ".join(parts)


def _expr_equal(left: Any, right: Any) -> bool:
    try:
        return bool(simplify(left - right) == 0)
    except Exception:
        return False


def _eq_tex(left: Any, right: Any) -> str:
    return f"{latex(left)} = {latex(right)}"


def _is_negative_number(val: Any) -> bool:
    try:
        return bool(getattr(val, "is_number", False) and val.is_number and val < 0)
    except Exception:
        return False


def _is_solved(lhs: Any, rhs: Any, var: Any) -> bool:
    return _expr_equal(lhs, var) and var not in getattr(rhs, "free_symbols", set())


def _independent(expr: Any, var: Any) -> Any:
    if not hasattr(expr, "as_independent"):
        return 0
    indep, _dep = expr.as_independent(var, as_Add=True)
    return indep


def _dependent(expr: Any, var: Any) -> Any:
    if not hasattr(expr, "as_independent"):
        return 0
    _indep, dep = expr.as_independent(var, as_Add=True)
    return dep


def _reciprocal_if_proper_fraction(coeff: Any) -> Any | None:
    """``x/2`` → multiply by 2, not divide by ``1/2``."""
    rat = simplify(coeff)
    if not getattr(rat, "is_number", False) or not getattr(rat, "is_rational", False):
        return None
    numer, denom = rat.as_numer_denom()
    if not getattr(numer, "is_integer", False) or not getattr(denom, "is_integer", False):
        return None
    if denom in (0, 1, -1):
        return None
    if abs(int(numer)) >= abs(int(denom)):
        return None
    return simplify(1 / rat)


def _latex_coeff(val: Any) -> str:
    tex = str(latex(val))
    if val.is_number and val < 0:
        return f"({tex})"
    return tex


def _is_symbol_power_product(expr: Any) -> bool:
    """``x`` / ``x^{2}`` / ``x y`` — not a leftover integer like ``8/2 → 4``."""
    if getattr(expr, "is_Symbol", False):
        return True
    if getattr(expr, "is_Pow", False):
        return bool(getattr(expr.base, "is_Symbol", False))
    if getattr(expr, "is_Mul", False):
        return all(_is_symbol_power_product(arg) for arg in expr.args)
    return False


def _cancelled_side_tex(side: Any, divisor: Any) -> str:
    """Strike matching factors when dividing ``3x`` by ``3``, not when ``8/2``."""
    d_tex = str(latex(divisor))
    if divisor == 0:
        return str(latex(side))
    if _expr_equal(side, divisor):
        return f"\\frac{{\\cancel{{{d_tex}}}}}{{\\cancel{{{d_tex}}}}}"
    try:
        rest = simplify(side / divisor)
    except Exception:
        return f"\\frac{{{latex(side)}}}{{{d_tex}}}"
    if _expr_equal(rest, 1) and _expr_equal(rest * divisor, side):
        return f"\\frac{{\\cancel{{{d_tex}}}}}{{\\cancel{{{d_tex}}}}}"
    if _is_symbol_power_product(rest) and _expr_equal(rest * divisor, side):
        return f"\\frac{{\\cancel{{{d_tex}}} {latex(rest)}}}{{\\cancel{{{d_tex}}}}}"
    return f"\\frac{{{latex(side)}}}{{{d_tex}}}"


def _divide_both_sides_step(
    cur_l: Any,
    cur_r: Any,
    coeff: Any,
    *,
    label: str | None = None,
    branch: str | None = None,
) -> KeyStep:
    return KeyStep(
        label=label or f"Divide both sides by {latex(coeff)}",
        formula=(f"{_cancelled_side_tex(cur_l, coeff)} = {_cancelled_side_tex(cur_r, coeff)}"),
        reason=f"this undoes multiplication by {latex(coeff)}",
        branch=branch,
    )


def _remove_term_step(
    cur_l: Any,
    cur_r: Any,
    term: Any,
    *,
    which: str | None = None,
    branch: str | None = None,
) -> KeyStep:
    if _is_negative_number(term):
        addend = -term
        label = f"Add {latex(addend)} to both sides"
        formula = f"{latex(cur_l)} + {latex(addend)} = {latex(cur_r)} + {latex(addend)}"
        reason = f"this cancels the subtracted {latex(addend)}"
    else:
        label = f"Subtract {latex(term)} from both sides"
        formula = f"{latex(cur_l)} - {latex(term)} = {latex(cur_r)} - {latex(term)}"
        reason = f"this removes the added {latex(term)}"
    if which is not None:
        label = f"{label} of the {which} equation"
    return KeyStep(label=label, formula=formula, reason=reason, branch=branch)


def _linear_key_steps(lhs: Any, rhs: Any, var: Any, poly: Any) -> list[KeyStep]:
    c1 = poly.coeff_monomial(var)
    c0 = poly.coeff_monomial(1)
    if c1 == 0:
        return []
    if _is_solved(lhs, rhs, var):
        return []
    steps: list[KeyStep] = []
    cur_l, cur_r = lhs, rhs
    exp_l, exp_r = expand(cur_l), expand(cur_r)
    if not _expr_equal(exp_l, cur_l) or not _expr_equal(exp_r, cur_r):
        steps.append(KeyStep(label="Expand", formula=_eq_tex(exp_l, exp_r)))
        cur_l, cur_r = exp_l, exp_r

    r_dep = _dependent(cur_r, var)
    if r_dep != 0:
        steps.append(_remove_term_step(cur_l, cur_r, r_dep))
        cur_l = simplify(cur_l - r_dep)
        cur_r = simplify(cur_r - r_dep)
        if not _is_solved(cur_l, cur_r, var):
            steps.append(KeyStep(label="Simplify", formula=_eq_tex(cur_l, cur_r)))

    l_indep = _independent(cur_l, var)
    if l_indep != 0:
        steps.append(_remove_term_step(cur_l, cur_r, l_indep))
        cur_l = simplify(cur_l - l_indep)
        cur_r = simplify(cur_r - l_indep)
        if not _is_solved(cur_l, cur_r, var):
            steps.append(KeyStep(label="Simplify", formula=_eq_tex(cur_l, cur_r)))

    coeff = cur_l.coeff(var) if hasattr(cur_l, "coeff") else c1
    if coeff == 0:
        return steps
    if coeff == -1:
        steps.append(
            KeyStep(
                label="Multiply both sides by -1",
                formula=_eq_tex(-cur_l, -cur_r),
                reason="this changes the sign of both sides",
            )
        )
        return steps
    if coeff != 1:
        multiplier = _reciprocal_if_proper_fraction(coeff)
        if multiplier is not None:
            steps.append(
                KeyStep(
                    label=f"Multiply both sides by {latex(multiplier)}",
                    formula=(
                        f"{latex(multiplier)} \\cdot ({latex(cur_l)}) = "
                        f"{latex(multiplier)} \\cdot ({latex(cur_r)})"
                    ),
                    reason="this clears the coefficient",
                )
            )
        else:
            steps.append(_divide_both_sides_step(cur_l, cur_r, coeff))
        return steps
    if not steps:
        isolated = simplify(-c0 / c1)
        return [
            KeyStep(
                label="Isolate",
                formula=f"{latex(c1)} \\cdot {var} = {latex(-c0)}",
            ),
            KeyStep(label="Solve", formula=f"{var} = {latex(isolated)}"),
        ]
    return steps


def _quadratic_key_steps(lhs: Any, rhs: Any, var: Any, poly: Any) -> list[KeyStep]:
    c2 = poly.coeff_monomial(var**2)
    c1 = poly.coeff_monomial(var)
    c0 = poly.coeff_monomial(1)
    if c2 == 0:
        return []
    if c1 == 0:
        return _pure_power_key_steps(lhs, rhs, var, c2, c0)
    expr = simplify(lhs - rhs)
    factored = factor(expr)
    if factored != expr and (factored.is_Mul or factored.is_Pow):
        return _factor_trace(lhs, rhs, var, expr, factored)
    return _quadratic_formula_steps(var, c2, c1, c0)


def _pure_power_key_steps(lhs: Any, rhs: Any, var: Any, c2: Any, c0: Any) -> list[KeyStep]:
    steps: list[KeyStep] = []
    cur_l, cur_r = lhs, rhs
    if var in getattr(cur_r, "free_symbols", set()):
        return []
    l_indep = _independent(cur_l, var)
    if l_indep != 0:
        steps.append(_remove_term_step(cur_l, cur_r, l_indep))
        cur_l = simplify(cur_l - l_indep)
        cur_r = simplify(cur_r - l_indep)
        if not _is_solved(cur_l, cur_r, var):
            steps.append(KeyStep(label="Simplify", formula=_eq_tex(cur_l, cur_r)))

    leading = cur_l.coeff(var**2) if hasattr(cur_l, "coeff") else c2
    if leading not in (0, 1, -1) and leading is not None:
        steps.append(_divide_both_sides_step(cur_l, cur_r, leading))
        cur_l = simplify(cur_l / leading)
        cur_r = simplify(cur_r / leading)
        steps.append(KeyStep(label="Simplify", formula=_eq_tex(cur_l, cur_r)))
    elif leading == -1:
        steps.append(
            KeyStep(
                label="Multiply both sides by -1",
                formula=_eq_tex(-cur_l, -cur_r),
            )
        )
        cur_l, cur_r = simplify(-cur_l), simplify(-cur_r)

    radicand = simplify(cur_r) if _expr_equal(cur_l, var**2) else simplify(-c0 / c2)
    if not getattr(radicand, "is_number", False) or not radicand.is_number:
        return steps
    if radicand < 0:
        return steps
    root = simplify(sqrt(radicand))
    steps.append(
        KeyStep(
            label="Take square roots of both sides",
            formula=rf"\sqrt{{{latex(var)}^{{2}}}} = \sqrt{{{latex(radicand)}}}",
        )
    )
    if radicand == 0:
        steps.append(
            KeyStep(
                label="Use absolute value",
                formula=rf"\lvert {latex(var)} \rvert = 0",
                reason="the square root of a square is the distance from zero",
            )
        )
        return steps
    steps.append(
        KeyStep(
            label="Use absolute value",
            formula=rf"\lvert {latex(var)} \rvert = {latex(root)}",
            reason=(
                "for real numbers, the square root of a square gives "
                "the number's distance from zero"
            ),
        )
    )
    return steps


def _linear_factors(factored: Any, var: Any) -> list[Any]:
    pieces: list[Any] = []
    if factored.is_Pow:
        base, _exp = factored.as_base_exp()
        pieces.append(base)
    elif factored.is_Mul:
        for arg in factored.args:
            if arg.is_Pow:
                pieces.append(arg.as_base_exp()[0])
            elif var in getattr(arg, "free_symbols", set()):
                pieces.append(arg)
    else:
        pieces.append(factored)
    linear: list[Any] = []
    for piece in pieces:
        poly = piece.as_poly(var) if hasattr(piece, "as_poly") else None
        if poly is not None and poly.degree() == 1:
            linear.append(piece)
    return linear


def _factor_trace(lhs: Any, rhs: Any, var: Any, expr: Any, factored: Any) -> list[KeyStep]:
    steps: list[KeyStep] = []
    if not _expr_equal(rhs, 0):
        steps.append(
            KeyStep(
                label="Rearrange",
                formula=_eq_tex(expr, 0),
                reason="factoring needs one side equal to zero",
            )
        )
    steps.append(
        KeyStep(
            label="Factor the left side",
            formula=_eq_tex(factored, 0),
        )
    )
    factors = _linear_factors(factored, var)
    if len(factors) < 1:
        return steps
    or_parts = [_eq_tex(piece, 0) for piece in factors]
    steps.append(
        KeyStep(
            label="Set each factor equal to zero",
            formula=r" \quad\text{or}\quad ".join(or_parts),
            reason="a product is zero when at least one factor is zero",
        )
    )
    ordinals = ("first", "second", "third")
    for index, piece in enumerate(factors):
        which = ordinals[index] if index < len(ordinals) else None
        branch = str(piece)
        indep = _independent(piece, var)
        cur_l, cur_r = piece, 0
        if indep != 0:
            steps.append(_remove_term_step(cur_l, cur_r, indep, which=which, branch=branch))
        coeff = piece.coeff(var) if hasattr(piece, "coeff") else 1
        if coeff not in (0, 1, -1):
            steps.append(
                _divide_both_sides_step(
                    simplify(piece - indep),
                    -indep,
                    coeff,
                    label=(
                        f"Divide both sides of the {which} equation by {latex(coeff)}"
                        if which
                        else f"Divide both sides by {latex(coeff)}"
                    ),
                    branch=branch,
                )
            )
    return steps


def _quadratic_formula_steps(var: Any, c2: Any, c1: Any, c0: Any) -> list[KeyStep]:
    discriminant = simplify(c1**2 - 4 * c2 * c0)
    if c2 == 1:
        denom = "2"
    elif c2 == -1:
        denom = "-2"
    else:
        denom = f"2({latex(c2)})"
    return [
        KeyStep(
            label="Discriminant",
            formula=(
                f"\\Delta = {_latex_coeff(c1)}^{{2}} - 4({latex(c2)})({latex(c0)}) "
                f"= {latex(discriminant)}"
            ),
        ),
        KeyStep(
            label="Quadratic formula",
            formula=(
                f"{var} = \\frac{{-{_latex_coeff(c1)} \\pm "
                f"\\sqrt{{{latex(discriminant)}}}}}{{{denom}}}"
            ),
        ),
    ]


def _substituted_eq(lhs: Any, rhs: Any, var: Any, val: Any) -> str:
    dummy = Symbol("QQQ")
    wrapped = f"({latex(val)})"
    left = latex(lhs.subs(var, dummy)).replace("QQQ", wrapped)
    if var in getattr(rhs, "free_symbols", set()):
        right = latex(rhs.subs(var, dummy)).replace("QQQ", wrapped)
    else:
        right = latex(rhs)
    return f"{left} = {right}"


def used_factor_trace(steps: list[KeyStep]) -> bool:
    return any(step.label.startswith("Factor") for step in steps)
