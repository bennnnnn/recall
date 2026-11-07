"""Limits: the value, then substitution, factor and cancel, L'Hôpital or the highest power."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.core.config import Settings
from app.modules.math import solve as math_solve
from app.modules.math.schemas import MathIntent
from app.modules.math.solve.declines import declines, sympy_decline
from app.modules.math.tools.block.canonical import finish_with_answer
from app.services.solving import VerifiedMathBlock
from app.services.workout import Workout, math_line, render_workout


def _verified_block_limit(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.limit_point is not None):
        return None
    limit_out = math_solve.compute_limit(
        intent.expr, intent.variable, intent.limit_point, intent.limit_direction
    )
    if limit_out.result == "zoo":
        message = "The two-sided limit does not exist because the one-sided limits disagree."
        lines.append(f"{message} Do not call it infinity.")
        return VerifiedMathBlock(text="\n".join(lines), direct_reply=message)
    lines.append(f"Result: {limit_out.latex}")
    if limit_out.is_infinite:
        lines.append(
            "This limit is infinite — preserve its sign, do not treat it as an ordinary "
            "finite number."
        )
    block = finish_with_answer(lines, limit_out.latex)
    if limit_out.is_infinite or intent.limit_direction not in (None, "+-"):
        return block  # a one-sided or infinite limit keeps the answer card alone
    working = _limit_working(intent, limit_out.latex)
    return replace(block, worked_reply=working) if working else block


def _limit_working(intent: MathIntent, answer: str) -> str | None:
    """Substitute; or factor and cancel a 0/0; or L'Hôpital's rule, round by round.

    Only a quotient as written is worked as 0/0: ``1/x - 1/sin x`` is ``∞ - ∞`` until
    it is combined, so it keeps its card alone.
    """
    from sympy import Expr, Symbol, cancel, factor, fraction, latex, limit, nan, simplify, zoo

    with sympy_decline() as declined:
        expr = math_solve.parse_expression(intent.expr or "", [intent.variable])
        written = str(intent.limit_point).strip().lower().replace("∞", "oo")
        # "infinity" is how the request names it; the parser would read a symbol.
        written = {"infinity": "oo", "+infinity": "oo", "-infinity": "-oo", "inf": "oo"}.get(
            written, written
        )
        point = math_solve.parse_expression(written, [])
        if not (isinstance(expr, Expr) and isinstance(point, Expr)):
            return None  # ``(1, 2)``, ``True`` or a bare SymPy name has no limit to work
        symbol = next(
            (s for s in expr.free_symbols if str(s) == intent.variable), Symbol(intent.variable)
        )
        value = limit(expr, symbol, point)
        if not value.is_finite:
            return None
        if point.is_infinite:
            return _limit_at_infinity_working(expr, symbol, point, value, answer)
        direct = expr.subs(symbol, point)
    if declined:
        return None
    var, at = latex(symbol), latex(point)
    lim = rf"\lim_{{{var} \to {at}}}"

    def operand(value: Any) -> str:
        """``\\lim (x + 1)``: a sum, or a leading minus, after the limit sign is bracketed."""
        shown = str(latex(value))
        return rf"\left({shown}\right)" if value.is_Add or shown.startswith("-") else shown

    find = (math_line(f"{lim} {operand(expr)}"),)
    substitute = f"substitute ${var} = {at}$"
    if direct.is_finite and not direct.has(nan, zoo) and simplify(direct - value) == 0:
        steps: tuple[str, ...] = (math_line(f"{lim} {operand(expr)} = {latex(value)}", substitute),)
        return render_workout(Workout(find=find, steps=steps), answer)
    numerator, denominator = fraction(expr)  # as written: no terms combined
    if denominator == 1 or simplify(numerator.subs(symbol, point)) != 0:
        return None
    if simplify(denominator.subs(symbol, point)) != 0:
        return None
    zero = math_line(r"\frac{0}{0}", f"substituting ${var} = {at}$ gives an indeterminate form")
    reduced = cancel(expr)
    if reduced != expr and simplify(reduced.subs(symbol, point) - value) == 0:
        factored = rf"\frac{{{latex(factor(numerator))}}}{{{latex(factor(denominator))}}}"
        steps = (
            zero,
            math_line(f"{latex(expr)} = {factored} = {latex(reduced)}", "factor and cancel"),
            math_line(f"{lim} {operand(reduced)} = {latex(value)}", substitute),
        )
        return render_workout(Workout(find=find, steps=steps), answer)
    rows = _lhopital_rows(numerator, denominator, symbol, point, value)
    if rows is None:
        return None
    rule = math_line(r"\lim \frac{f}{g} = \lim \frac{f'}{g'}", "L'Hôpital's rule, for a 0/0 limit")
    first, *more = rows
    steps = (
        zero,
        math_line(f"{lim} {operand(expr)} = {first}", "differentiate the top and the bottom"),
        *(math_line(f"= {row}", "$\\frac{0}{0}$ again: differentiate again") for row in more),
        math_line(f"= {latex(value)}", substitute),
    )
    return render_workout(Workout(find=find, formula=(rule,), steps=steps), answer)


# A school 0/0 limit settles within three rounds: (1 - cos x)/x^2 takes two.
_LHOPITAL_ROUNDS = 3


@declines(None)
def _lhopital_rows(
    numerator: Any, denominator: Any, symbol: Any, point: Any, value: Any
) -> list[str] | None:
    """``\\lim \\frac{f'}{g'}`` for each round of L'Hôpital's rule, until one substitutes.

    Each round is shown only when SymPy confirms its limit is the limit asked; a round
    that is still 0/0 differentiates again, and one that is neither declines.
    """
    from sympy import diff, latex, limit, simplify

    lim = rf"\lim_{{{latex(symbol)} \to {latex(point)}}}"
    rows: list[str] = []
    top, bottom = numerator, denominator
    for _ in range(_LHOPITAL_ROUNDS):
        # Simplified, so a round reads as a student writes it: 2 tan x / cos^2 x.
        top, bottom = simplify(diff(top, symbol)), simplify(diff(bottom, symbol))
        if simplify(limit(top / bottom, symbol, point) - value) != 0:
            return None
        rows.append(rf"{lim} \frac{{{latex(top)}}}{{{latex(bottom)}}}")
        at_top, at_bottom = simplify(top.subs(symbol, point)), simplify(bottom.subs(symbol, point))
        if at_bottom != 0 and at_bottom.is_finite and at_top.is_finite:
            return rows if simplify(at_top / at_bottom - value) == 0 else None
        if at_top != 0 or at_bottom != 0:
            return None
    return None


def _limit_at_infinity_working(
    expr: Any, symbol: Any, point: Any, value: Any, answer: str
) -> str | None:
    """Divide by the highest power, or name the limit that defines ``e``.

    ``\\frac{3x^2 + 1}{x^2 - 2}``: over ``x^2`` top and bottom it is
    ``\\frac{3 + 1/x^2}{1 - 2/x^2}``, and each ``1/x^k`` goes to 0.
    """
    from sympy import Add, Poly, expand, latex, limit, simplify

    lim = rf"\lim_{{{latex(symbol)} \to {latex(point)}}}"
    find = (math_line(f"{lim} {latex(expr)}"),)
    if expr.is_Pow:
        base_gap = simplify((expr.base - 1) * symbol)
        power = simplify(expr.exp / symbol)
        if not base_gap.has(symbol) and not power.has(symbol) and base_gap != 0:
            row = math_line(
                f"{lim} {latex(expr)} = {latex(value)}",
                r"the limit that defines $e$: $\left(1 + \frac{k}{n}\right)^{n} \to e^{k}$",
            )
            return render_workout(Workout(find=find, steps=(row,)), answer)
        return None
    numerator, denominator = expr.as_numer_denom()
    with sympy_decline() as declined:
        top_degree = Poly(numerator, symbol).degree()
        bottom_degree = Poly(denominator, symbol).degree()
    if declined:
        return None
    if bottom_degree < 1 or top_degree > bottom_degree:
        return None
    scale = symbol**bottom_degree

    def shown(part: Any, *, vanish: bool) -> str:
        terms = Add.make_args(expand(part / scale))
        pieces: list[str] = []
        for term in sorted(terms, key=lambda term: -Poly(term * scale, symbol).degree()):
            gone = vanish and term.has(symbol) and limit(term, symbol, point) == 0
            text = "0" if gone else latex(-term if term.could_extract_minus_sign() else term)
            sign = "-" if term.could_extract_minus_sign() else "+"
            pieces.append(text if not pieces and sign == "+" else f"{sign} {text}")
        return " ".join(pieces).lstrip("+ ")

    divided = rf"\frac{{{shown(numerator, vanish=False)}}}{{{shown(denominator, vanish=False)}}}"
    limits = rf"\frac{{{shown(numerator, vanish=True)}}}{{{shown(denominator, vanish=True)}}}"
    rows = (
        math_line(
            f"{lim} {latex(expr)} = {lim} {divided}",
            f"divide the top and the bottom by ${latex(scale)}$",
        ),
        math_line(f"= {limits}", f"each $\\frac{{1}}{{{latex(symbol)}^k}} \\to 0$"),
    )
    return render_workout(Workout(find=find, steps=rows), answer)
