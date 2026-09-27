"""Verified inverse-operation traces for linear, pure-power, and quadratic equations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sympy import (
    Abs,
    Eq,
    Poly,
    S,
    Symbol,
    expand,
    factor,
    im,
    latex,
    log,
    prod,
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


_PLAIN_LABEL_TEX = re.compile(r"^[\w .,-]*$")


def label_tex(value: Any) -> str:
    """A value inside a step label: ``3`` stays plain, ``\\frac{3}{2}`` gets ``$``.

    Labels render as bold text, so LaTeX markup needs math delimiters to show
    as math; plain numbers and terms read the same either way.
    """
    tex = str(latex(value))
    return tex if _PLAIN_LABEL_TEX.match(tex) else f"${tex}$"


def stringify_key_steps(steps: list[KeyStep]) -> list[str]:
    return [f"{step.label}: {step.formula}" for step in steps]


def equation_key_steps(
    lhs: Any,
    rhs: Any,
    variable: str,
    *,
    force_quadratic_formula: bool = False,
) -> list[KeyStep]:
    """Structured working from the original sides. Empty when the shape is unsupported."""
    symbols = getattr(lhs, "free_symbols", set()) | getattr(rhs, "free_symbols", set())
    var = next((symbol for symbol in symbols if str(symbol) == variable), Symbol(variable))
    logarithm_steps = _logarithm_key_steps(lhs, rhs, var)
    if logarithm_steps is not None:
        return logarithm_steps
    absolute_steps = _absolute_value_key_steps(lhs, rhs, var)
    if absolute_steps is not None:
        return absolute_steps
    radical_steps = _radical_equation_key_steps(lhs, rhs, var)
    if radical_steps is not None:
        return radical_steps
    fractional_power_steps = _fractional_power_key_steps(lhs, rhs, var)
    if fractional_power_steps is not None:
        return fractional_power_steps
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
        return _quadratic_key_steps(
            lhs,
            rhs,
            var,
            poly,
            force_formula=force_quadratic_formula,
        )
    return []


def _radical_equation_key_steps(lhs: Any, rhs: Any, var: Any) -> list[KeyStep] | None:
    """Trace one or two square roots, including the extraneous-root check."""
    two_radicals = _two_radical_equation_key_steps(lhs, rhs, var)
    if two_radicals is not None:
        return two_radicals
    radical, other = lhs, rhs
    if not (getattr(radical, "is_Pow", False) and radical.exp == S.Half):
        if getattr(rhs, "is_Pow", False) and rhs.exp == S.Half:
            radical, other = rhs, lhs
        else:
            return None
    radicand = radical.base
    if var not in getattr(radicand, "free_symbols", set()):
        return None
    try:
        squared = Eq(radicand, expand(other**2))
        candidates = solve(squared, var)
        valid = [
            value
            for value in candidates
            if _expr_equal(radical.subs(var, value), other.subs(var, value))
        ]
    except Exception:
        return []
    if not candidates or not valid:
        return []
    domain = rf"{latex(radicand)} \ge 0 \quad\text{{and}}\quad {latex(other)} \ge 0"
    return [
        KeyStep(label="Domain restrictions", formula=domain),
        KeyStep(label="Square both sides", formula=_eq_tex(radicand, expand(other**2))),
        KeyStep(
            label="Solve the squared equation",
            formula=_canonical_root_formula(var, candidates),
        ),
        KeyStep(
            label="Check and reject extraneous roots",
            formula=_canonical_root_formula(var, valid),
        ),
    ]


def _two_radical_equation_key_steps(lhs: Any, rhs: Any, var: Any) -> list[KeyStep] | None:
    """Verified repeated-squaring trace for ``sqrt(a)+sqrt(b)=constant``."""
    radical_side, target = lhs, rhs
    terms = radical_side.args if getattr(radical_side, "is_Add", False) else ()
    radicals = [term for term in terms if getattr(term, "is_Pow", False) and term.exp == S.Half]
    if len(terms) != 2 or len(radicals) != 2:
        radical_side, target = rhs, lhs
        terms = radical_side.args if getattr(radical_side, "is_Add", False) else ()
        radicals = [term for term in terms if getattr(term, "is_Pow", False) and term.exp == S.Half]
    if len(terms) != 2 or len(radicals) != 2:
        return None
    if var in getattr(target, "free_symbols", set()) or simplify(target) == 0:
        return None
    first, second = radicals
    first_base, second_base = first.base, second.base
    try:
        isolated = simplify((target**2 + second_base - first_base) / (2 * target))
        candidates = solve(Eq(second_base, isolated**2), var)
        valid = [
            value
            for value in candidates
            if _expr_equal(radical_side.subs(var, value), target.subs(var, value))
        ]
    except Exception:
        return []
    if not candidates or not valid:
        return []
    domain = (
        rf"{latex(first_base)} \ge 0,\quad {latex(second_base)} \ge 0,"
        rf"\quad {latex(target)} \ge 0"
    )
    return [
        KeyStep(label="Domain restrictions", formula=domain),
        KeyStep(
            label="Isolate one radical",
            formula=_eq_tex(first, target - second),
        ),
        KeyStep(
            label="Square and isolate the remaining radical",
            formula=_eq_tex(2 * target * second, target**2 + second_base - first_base),
        ),
        KeyStep(
            label="Square again",
            formula=_eq_tex(second_base, isolated**2),
        ),
        KeyStep(
            label="Check in the original equation",
            formula=_canonical_root_formula(var, valid),
        ),
    ]


def _fractional_power_key_steps(lhs: Any, rhs: Any, var: Any) -> list[KeyStep] | None:
    power, target = lhs, rhs
    if not (getattr(power, "is_Pow", False) and power.base == var):
        if getattr(rhs, "is_Pow", False) and rhs.base == var:
            power, target = rhs, lhs
        else:
            return None
    exponent = power.exp
    if not (getattr(exponent, "is_Rational", False) and exponent.q != 1 and exponent.q % 2 == 1):
        return None
    from app.modules.math.solve.algebra import _real_fractional_power_solutions

    solutions = _real_fractional_power_solutions(power, target, var)
    if not solutions:
        return []
    equivalent = Eq(var ** int(exponent.p), simplify(target ** int(exponent.q)))
    return [
        KeyStep(
            label="Use the real odd-root interpretation",
            formula=(
                rf"{latex(power)} = \left(\sqrt[{exponent.q}]{{{latex(var)}}}\right)"
                rf"^{{{exponent.p}}}"
            ),
        ),
        KeyStep(
            label=f"Raise both sides to the {exponent.q}rd power"
            if exponent.q == 3
            else f"Raise both sides to the {exponent.q}th power",
            formula=latex(equivalent),
        ),
        KeyStep(label="Solve over the reals", formula=_canonical_root_formula(var, solutions)),
    ]


def _logarithm_key_steps(lhs: Any, rhs: Any, var: Any) -> list[KeyStep] | None:
    """Verified trace for a sum of same-base logarithms."""
    if var in getattr(rhs, "free_symbols", set()):
        return None
    terms = lhs.args if getattr(lhs, "is_Add", False) else (lhs,)
    arguments: list[Any] = []
    base: Any | None = None
    for term in terms:
        numerator, denominator = term.as_numer_denom()
        if getattr(numerator, "func", None) is not log:
            return None
        if getattr(denominator, "func", None) is not log or len(denominator.args) != 1:
            return None
        candidate_base = denominator.args[0]
        if base is not None and not _expr_equal(base, candidate_base):
            return None
        base = candidate_base
        arguments.append(numerator.args[0])
    if base is None or not arguments:
        return None
    try:
        combined = prod(arguments)
        target = simplify(base**rhs)
        candidates = solve(Eq(combined, target), var)
        valid = [
            value
            for value in candidates
            if all(bool(simplify(argument.subs(var, value)) > 0) for argument in arguments)
        ]
    except Exception:
        return []
    if not candidates or not valid:
        return []
    domain = r" \text{ and } ".join(rf"{latex(argument)} > 0" for argument in arguments)
    candidate_formula = _canonical_root_formula(var, candidates)
    answer = _canonical_root_formula(var, valid)
    base_tex = latex(base)
    return [
        KeyStep(label="Domain restriction", formula=domain),
        KeyStep(
            label="Combine logarithms",
            formula=rf"\log_{{{base_tex}}}\left({latex(combined)}\right) = {latex(rhs)}",
        ),
        KeyStep(
            label="Convert to exponential form",
            formula=rf"{latex(combined)} = {latex(target)}",
        ),
        KeyStep(label="Solve the resulting equation", formula=candidate_formula),
        KeyStep(label="Reject values outside the domain", formula=answer),
    ]


def _rational_equation_key_steps(lhs: Any, rhs: Any, var: Any) -> list[KeyStep] | None:
    left_num, left_den = getattr(lhs, "as_numer_denom", lambda: (lhs, 1))()
    right_num, right_den = getattr(rhs, "as_numer_denom", lambda: (rhs, 1))()
    left_has_variable_denominator = var in getattr(left_den, "free_symbols", set())
    right_has_variable_denominator = var in getattr(right_den, "free_symbols", set())
    if not left_has_variable_denominator and not right_has_variable_denominator:
        return None
    try:
        from sympy import Mul

        denominator = simplify(left_den * right_den)
        cleared_lhs = simplify(lhs * denominator)
        cleared_rhs = simplify(rhs * denominator)
        display_lhs = left_num if right_den == 1 else Mul(left_num, right_den, evaluate=False)
        display_rhs = right_num if left_den == 1 else Mul(right_num, left_den, evaluate=False)
        multiplied = _eq_tex(display_lhs, display_rhs)
        poly = Poly(simplify(cleared_lhs - cleared_rhs), var)
        if poly.degree() < 1:
            return []
        den_poly = denominator.as_poly(var) if hasattr(denominator, "as_poly") else None
        den_degree = den_poly.degree() if den_poly is not None else None
        from app.core.config import get_settings

        degree_cap = get_settings().math_max_poly_degree
        high_denominator = den_degree is None or int(den_degree) > degree_cap
        candidates = solve(Eq(cleared_lhs, cleared_rhs), var)
        if high_denominator:
            # Do not ask SymPy for every root of a huge denominator.
            # A plain int has no .subs; the variable-denominator path is an expression.
            if isinstance(denominator, int):
                return []
            excluded = []
            solutions = [
                solution
                for solution in candidates
                if simplify(denominator.subs(var, solution)) != 0
            ]
        else:
            excluded = solve(Eq(denominator, 0), var)
            solutions = [
                solution
                for solution in candidates
                if all(not _expr_equal(solution, value) for value in excluded)
            ]
    except Exception:
        return []
    condition = r"\text{denominator} \ne 0"
    if high_denominator:
        exclusions_tex = condition
    elif excluded:
        exclusions_tex = r",\; ".join(rf"{latex(var)} \ne {latex(value)}" for value in excluded)
    else:
        exclusions_tex = condition
    steps = [
        KeyStep(label="Domain restrictions", formula=exclusions_tex),
        KeyStep(
            label=f"Multiply both sides by {label_tex(denominator)}",
            formula=multiplied,
        ),
    ]
    if candidates:
        steps.append(
            KeyStep(
                label="Solve the resulting equation",
                formula=_canonical_root_formula(var, candidates),
            )
        )
    if solutions:
        final = _canonical_root_formula(var, solutions)
        if len(solutions) != len(candidates):
            steps.append(KeyStep(label="Reject excluded values", formula=final))
    else:
        steps.append(
            KeyStep(
                label="Reject the excluded candidate",
                formula=r"\text{no solution}",
            )
        )
    return steps


def _absolute_value_key_steps(lhs: Any, rhs: Any, var: Any) -> list[KeyStep] | None:
    if getattr(rhs, "func", None) is Abs and getattr(lhs, "func", None) is not Abs:
        lhs, rhs = rhs, lhs
    if getattr(lhs, "func", None) is not Abs:
        return None
    if var in getattr(rhs, "free_symbols", set()) or not getattr(rhs, "is_number", False):
        return []
    try:
        if rhs < 0 or Poly(lhs.args[0], var).degree() != 1:
            return []
        solutions = solve(Eq(lhs, rhs), var)
    except Exception:
        return []
    if not solutions:
        return []
    inside = lhs.args[0]
    # |u|=c splits into u=±c only when u is real. |x+I|=5 is a modulus, not that split.
    try:
        if simplify(im(inside)) != 0:
            return []
    except Exception:
        return []
    split = _eq_tex(inside, rhs)
    if rhs != 0:
        split += rf" \quad\text{{or}}\quad {_eq_tex(inside, -rhs)}"
    from app.modules.math.solve.algebra import compact_root_answer_lines

    lines = compact_root_answer_lines(str(var), solutions)
    final = lines[0] if len(lines) == 1 else r" \text{ or } ".join(lines)
    return [
        KeyStep(label="Split the absolute-value equation", formula=split),
        KeyStep(label="Solve both linear equations", formula=final),
    ]


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


def _canonical_root_formula(var: Any, solutions: list[Any]) -> str:
    from app.modules.math.solve.algebra import compact_root_answer_lines

    lines = compact_root_answer_lines(str(var), solutions)
    return lines[0] if len(lines) == 1 else r" \text{ or } ".join(lines)


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
        label=label or f"Divide both sides by {label_tex(coeff)}",
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
        label = f"Add {label_tex(addend)} to both sides"
        formula = f"{latex(cur_l)} + {latex(addend)} = {latex(cur_r)} + {latex(addend)}"
        reason = f"this cancels the subtracted {latex(addend)}"
    else:
        label = f"Subtract {label_tex(term)} from both sides"
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
                    label=f"Multiply both sides by {label_tex(multiplier)}",
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


def _quadratic_key_steps(
    lhs: Any,
    rhs: Any,
    var: Any,
    poly: Any,
    *,
    force_formula: bool = False,
) -> list[KeyStep]:
    c2 = poly.coeff_monomial(var**2)
    c1 = poly.coeff_monomial(var)
    c0 = poly.coeff_monomial(1)
    if c2 == 0:
        return []
    if c1 == 0:
        return _pure_power_key_steps(lhs, rhs, var, c2, c0)
    expr = simplify(lhs - rhs)
    factored = factor(expr)
    if not force_formula and factored != expr and (factored.is_Mul or factored.is_Pow):
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
        steps.append(
            KeyStep(
                label="Take square roots of both sides",
                formula=rf"{latex(var)} = \pm \sqrt{{{latex(radicand)}}}",
            )
        )
        # Raw sqrt() puts i in the numerator. The chip uses the canonical
        # conjugate form, so the last step has to come from that formatter.
        solutions = solve(Eq(var**2, radicand), var)
        from app.modules.math.solve.algebra import compact_root_answer_lines

        lines = compact_root_answer_lines(str(var), solutions)
        if lines:
            formula = lines[0] if len(lines) == 1 else r" \text{ or } ".join(lines)
            steps.append(KeyStep(label="Simplify", formula=formula))
        return steps
    # Show the root operation, then make any reduction its own final step.
    # That keeps the last displayed equation identical to the answer chip
    # without hiding the root that produced it.
    if radicand == 0:
        steps.append(KeyStep(label="Square root", formula=rf"{latex(var)} = \sqrt{{0}}"))
        steps.append(KeyStep(label="Simplify", formula=rf"{latex(var)} = 0"))
        return steps
    written = rf"\sqrt{{{latex(radicand)}}}"
    steps.append(KeyStep(label="Square root", formula=rf"{latex(var)} = \pm {written}"))
    reduced = latex(simplify(sqrt(radicand)))
    if reduced != written:
        steps.append(KeyStep(label="Simplify", formula=rf"{latex(var)} = \pm {reduced}"))
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
                        f"Divide both sides of the {which} equation by {label_tex(coeff)}"
                        if which
                        else f"Divide both sides by {label_tex(coeff)}"
                    ),
                    branch=branch,
                )
            )
    solutions = solve(Eq(expr, 0), var)
    if len(solutions) == 2 and _expr_equal(solutions[0] + solutions[1], 0):
        positive = simplify(Abs(solutions[0]))
        final = rf"{latex(var)} = \pm {latex(positive)}"
    else:
        final = r" \text{ or } ".join(f"{latex(var)} = {latex(solution)}" for solution in solutions)
    if final:
        steps.append(KeyStep(label="Simplify", formula=final))
    return steps


def _quadratic_formula_steps(var: Any, c2: Any, c1: Any, c0: Any) -> list[KeyStep]:
    discriminant = simplify(c1**2 - 4 * c2 * c0)
    if c2 == 1:
        denom = "2"
    elif c2 == -1:
        denom = "-2"
    else:
        denom = f"2({latex(c2)})"
    steps = [
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
    solutions = solve(Eq(c2 * var**2 + c1 * var + c0, 0), var)
    final = _canonical_root_formula(var, solutions)
    if final:
        steps.append(KeyStep(label="Simplify", formula=final))
    return steps


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
