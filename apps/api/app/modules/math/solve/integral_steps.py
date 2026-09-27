"""Method-by-method antiderivative lessons, checked by differentiating back.

For each part of an indefinite integral the method is read from structure:
the power rule, a standard antiderivative, u-substitution (the integrand is
``f(g(x)) g'(x)`` up to a constant), or integration by parts (a polynomial
times an exponential or trig factor, or a logarithm). Every antiderivative a
line states is differentiated back to its integrand with SymPy; a line that
fails that check drops the whole trace.
"""

from __future__ import annotations

from typing import Any

from sympy import (
    Add,
    Dummy,
    Poly,
    Symbol,
    cos,
    diff,
    exp,
    integrate,
    latex,
    log,
    preorder_traversal,
    simplify,
    sin,
)

from app.modules.math.solve.key_steps import KeyStep

_MAX_TERMS = 6
_POWER_REASON = r"$\int x^n\,dx = \frac{x^{n+1}}{n+1}$ for $n \ne -1$"
_PARTS_REASON = r"$\int u\,dv = uv - \int v\,du$"
_SUBSTITUTION_REASON = "the integrand is a function of u times du"


def _int(body: Any, var: Any) -> str:
    return rf"\int {_factor(body)}\,d{latex(var)}"


def _factor(expr: Any) -> str:
    tex = str(latex(expr))
    if expr.is_Add:
        return rf"\left({tex}\right)"
    return tex


def _differential(value: Any, var: Any) -> str:
    """``2 x\\,dx``; ``dx`` alone for a coefficient of one."""
    dx = rf"d{latex(var)}"
    return dx if value == 1 else rf"{_factor(value)}\,{dx}"


def split_sum(parts: list[str], negatives: list[bool]) -> str:
    """``A + B - C`` from rendered parts, a minus instead of ``+ -``."""
    text = parts[0]
    for part, negative in zip(parts[1:], negatives[1:], strict=True):
        text += f" - {part}" if negative else f" + {part}"
    return text


def _is_const(expr: Any, var: Any) -> bool:
    return var not in getattr(expr, "free_symbols", set())


def _antiderivative_of(candidate: Any, integrand: Any, var: Any) -> bool:
    try:
        return bool(simplify(diff(candidate, var) - integrand) == 0)
    except Exception:
        return False


def _power_step(term: Any, var: Any) -> tuple[KeyStep, Any] | None:
    coefficient, rest = term.as_coeff_Mul() if term.is_Mul else (1, term)
    if rest == var:
        power = 1
    elif rest.is_Pow and rest.base == var and _is_const(rest.exp, var) and rest.exp != -1:
        power = rest.exp
    else:
        return None
    result = coefficient * var ** (power + 1) / (power + 1)
    if not _antiderivative_of(result, term, var):
        return None
    multiplier = "" if coefficient == 1 else f"{latex(coefficient)} \\cdot "
    shown = rf"{multiplier}\frac{{{latex(var)}^{{{latex(power + 1)}}}}}{{{latex(power + 1)}}}"
    value = latex(result)
    formula = f"{_int(term, var)} = {value}"
    if shown.replace(" ", "") != value.replace(" ", ""):
        formula = f"{_int(term, var)} = {shown} = {value}"
    return (
        KeyStep(label=f"Power rule on ${latex(rest)}$", formula=formula, reason=_POWER_REASON),
        result,
    )


_STANDARD = {
    sin: (lambda arg: -cos(arg), r"$\int \sin x\,dx = -\cos x$"),
    cos: (lambda arg: sin(arg), r"$\int \cos x\,dx = \sin x$"),
    exp: (lambda arg: exp(arg), r"$\int e^x\,dx = e^x$"),
}


def _standard_step(term: Any, var: Any) -> tuple[KeyStep, Any] | None:
    coefficient, rest = term.as_coeff_Mul() if term.is_Mul else (1, term)
    if rest == 1 / var:
        result = coefficient * log(var)
        reason = r"$\int \frac{1}{x}\,dx = \ln x$"
    else:
        func: Any = getattr(rest, "func", None)
        if func is None or func not in _STANDARD or rest.args != (var,):
            return None
        antiderivative, reason = _STANDARD[func]
        result = coefficient * antiderivative(var)
    if not _antiderivative_of(result, term, var):
        return None
    return (
        KeyStep(
            label=f"Standard integral of ${latex(rest)}$",
            formula=f"{_int(term, var)} = {latex(result)}",
            reason=reason,
        ),
        result,
    )


def _inner_candidates(term: Any, var: Any) -> list[Any]:
    """Inside expressions worth trying as u, largest first."""
    found: list[Any] = []
    for node in preorder_traversal(term):
        if getattr(node, "is_Pow", False):
            inner = node.base
        elif getattr(node, "func", None) in (exp, sin, cos, log):
            inner = node.args[0]
        else:
            continue
        if inner != var and not _is_const(inner, var) and inner not in found:
            found.append(inner)
    return sorted(found, key=lambda expr: -expr.count_ops())


def _substitution_steps(term: Any, var: Any) -> tuple[list[KeyStep], Any] | None:
    u = Dummy("u")
    for inner in _inner_candidates(term, var):
        d_inner = diff(inner, var)
        if d_inner == 0:
            continue
        rest = simplify(term / d_inner)
        in_u = rest.xreplace({inner: u})
        if var in in_u.free_symbols:
            continue
        antiderivative_u = integrate(in_u, u)
        if antiderivative_u.has(integrate) or not antiderivative_u.free_symbols <= {u}:
            continue
        result = antiderivative_u.xreplace({u: inner})
        if not _antiderivative_of(result, term, var):
            continue
        shown_u = Symbol("u")
        in_shown = in_u.xreplace({u: shown_u})
        antiderivative_shown = antiderivative_u.xreplace({u: shown_u})
        steps = [
            KeyStep(
                label=f"Let $u = {latex(inner)}$",
                formula=rf"u = {latex(inner)}, \quad du = {_differential(d_inner, var)}",
                reason="the derivative of the inside is also in the integrand",
            ),
            KeyStep(
                label="Rewrite the integral in $u$",
                formula=rf"{_int(term, var)} = \int {_factor(in_shown)}\,du",
                reason=_SUBSTITUTION_REASON,
            ),
            KeyStep(
                label="Integrate in $u$",
                formula=rf"\int {_factor(in_shown)}\,du = {latex(antiderivative_shown)}",
            ),
            KeyStep(label=f"Put back $u = {latex(inner)}$", formula=latex(result)),
        ]
        return steps, result
    return None


def _parts_split(term: Any, var: Any) -> tuple[Any, Any] | None:
    """(u, dv) by LIATE for polynomial·exp/sin/cos and polynomial·log."""
    factors = list(term.args) if term.is_Mul else [term]
    logs = [f for f in factors if getattr(f, "func", None) is log and f.args == (var,)]
    if logs:
        dv = simplify(term / logs[0])
        try:
            if not _is_const(dv, var) and Poly(dv, var).degree() > 3:
                return None
        except Exception:
            return None
        return logs[0], dv
    transcendental = [
        f for f in factors if getattr(f, "func", None) in (exp, sin, cos) and not _is_const(f, var)
    ]
    if len(transcendental) != 1:
        return None
    polynomial = simplify(term / transcendental[0])
    try:
        degree = Poly(polynomial, var).degree()
    except Exception:
        return None
    if degree < 1 or degree > 2:
        return None
    inner = transcendental[0].args[0]
    try:
        if Poly(inner, var).degree() != 1:
            return None
    except Exception:
        return None
    return polynomial, transcendental[0]


def _parts_steps(term: Any, var: Any) -> tuple[list[KeyStep], Any] | None:
    split = _parts_split(term, var)
    if split is None:
        return None
    u, dv = split
    du = diff(u, var)
    v = integrate(dv, var)
    if v.has(integrate) or not _antiderivative_of(v, dv, var):
        return None
    remaining = simplify(v * du)
    remaining_integral = integrate(remaining, var)
    result = u * v - remaining_integral
    if remaining_integral.has(integrate) or not _antiderivative_of(result, term, var):
        return None
    dx = rf"\,d{latex(var)}"
    # Shown with its sign pulled out: ``- \int v\,du`` or ``+ \int (-v)\,du``.
    negative = remaining.could_extract_minus_sign()
    rest = -remaining if negative else remaining
    rest_integral = -remaining_integral if negative else remaining_integral
    rest_shown = rf"{'+' if negative else '-'} \int {_factor(rest)}{dx}"
    steps = [
        KeyStep(
            label=f"Choose $u = {latex(u)}$ and $dv = {_differential(dv, var)}$",
            formula=rf"du = {_differential(du, var)}, \quad v = {latex(v)}",
            reason="u gets simpler when differentiated; dv is easy to integrate",
        ),
        KeyStep(
            label="Apply integration by parts",
            formula=rf"{_int(term, var)} = {latex(u * v)} {rest_shown}",
            reason=_PARTS_REASON,
        ),
        KeyStep(
            label="Integrate what is left",
            formula=rf"\int {_factor(rest)}{dx} = {latex(rest_integral)}",
        ),
        KeyStep(label="Combine", formula=latex(result)),
    ]
    return steps, result


def _term_steps(term: Any, var: Any) -> tuple[list[KeyStep], Any] | None:
    if _is_const(term, var):
        result = term * var
        return (
            [
                KeyStep(
                    label=f"Integrate the constant ${latex(term)}$",
                    formula=f"{_int(term, var)} = {latex(result)}",
                )
            ],
            result,
        )
    for method in (_power_step, _standard_step):
        found = method(term, var)
        if found is not None:
            return [found[0]], found[1]
    for multi in (_substitution_steps, _parts_steps):
        steps = multi(term, var)
        if steps is not None:
            return steps
    return None


def integral_key_steps(expr: Any, variable: str) -> tuple[list[KeyStep], Any | None]:
    """Indefinite integral, one method per line. Returns (steps, antiderivative).

    The antiderivative may differ from SymPy's own by a constant; both are
    checked by differentiating back to ``expr``. ([], None) when a part's
    method is not recognized.
    """
    var = next((s for s in getattr(expr, "free_symbols", set()) if str(s) == variable), None)
    if var is None:
        return [], None
    terms = expr.as_ordered_terms() if isinstance(expr, Add) else [expr]
    if len(terms) > _MAX_TERMS:
        return [], None
    steps: list[KeyStep] = []
    if len(terms) > 1:
        negatives = [term.could_extract_minus_sign() for term in terms]
        split = split_sum(
            [
                _int(-term if negative else term, var)
                for term, negative in zip(terms, negatives, strict=True)
            ],
            negatives,
        )
        steps.append(
            KeyStep(
                label="Integrate term by term",
                formula=f"{_int(expr, var)} = {split}",
                reason="the integral of a sum is the sum of the integrals",
            )
        )
    parts: list[Any] = []
    for term in terms:
        found = _term_steps(term, var)
        if found is None:
            return [], None
        term_steps, antiderivative = found
        steps.extend(term_steps)
        parts.append(antiderivative)
    total = Add(*parts)
    if not _antiderivative_of(total, expr, var):
        return [], None
    if len(terms) > 1:
        steps.append(
            KeyStep(
                label="Add the results and the constant of integration",
                formula=f"{latex(total)} + C",
                reason="every antiderivative differs from this one by a constant",
            )
        )
    else:
        last = steps[-1]
        steps[-1] = KeyStep(
            label=last.label,
            formula=f"{last.formula} + C",
            reason=last.reason,
        )
    return steps, total


def integral_trace(expr: str, variable: str) -> tuple[list[KeyStep], str | None, str | None]:
    """Parse, then trace: (steps, problem LaTeX, checked answer ``F + C``)."""
    from app.modules.math.solve.parse import _parse_expression

    try:
        parsed = _parse_expression(expr, [variable])
    except Exception:
        return [], None, None
    steps, antiderivative = integral_key_steps(parsed, variable)
    if not steps or antiderivative is None or len(steps) < 2:
        return [], None, None
    var = next((s for s in parsed.free_symbols if str(s) == variable), Symbol(variable))
    return steps, _int(parsed, var), f"{latex(antiderivative)} + C"
