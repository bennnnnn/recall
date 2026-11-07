"""A matrix question that lists several results: each one worked, and one card with them all.

"Find the determinant and inverse of [[2,1],[5,3]]" reads two operations. Each is
computed by ``compute_matrix``; the working shows the determinant by its expansion and
the inverse as the adjugate over the determinant, each line checked against SymPy, and
the card holds ``\\det(A) = 1,\\quad A^{-1} = …``: never one result for the question.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.modules.math import solve as math_solve
from app.modules.math.schemas import MathIntent, MatrixInput
from app.modules.math.schemas.operations import MatrixOp
from app.modules.math.tools.block.canonical import finish_with_answer
from app.services.solving import VerifiedMathBlock
from app.services.workout import Workout, math_line, render_workout, text_line

# How the card and the working name each result of the matrix A.
_NAMES: dict[MatrixOp, str] = {
    "determinant": r"\det(A)",
    "inverse": "A^{-1}",
    "transpose": "A^{T}",
    "rank": r"\operatorname{rank}(A)",
    "rref": r"\operatorname{rref}(A)",
    "eigenvalues": r"\lambda(A)",
    "nullspace": r"\operatorname{Null}(A)",
    "columnspace": r"\operatorname{Col}(A)",
    "rowspace": r"\operatorname{Row}(A)",
}
# These results name their own parts (``E_{1}(A) = …``, ``P = …,\quad D = …``).
_SELF_NAMED = frozenset({"eigenvectors", "diagonalize"})


def _named_parts(op: MatrixOp, value: str) -> str:
    r"""Each part said as A's: ``\lambda=1:\ span{…}`` is the eigenspace ``E_{1}(A)``."""
    if op == "diagonalize":
        return f"A = PDP^{{-1}}:\\ {value}"
    spaces = []
    for part in value.split(r";\quad "):
        head, basis = part.split(r":\ ", 1)
        spaces.append(f"E_{{{head.removeprefix(r'\lambda=')}}}(A) = {basis}")
    return ",\\quad ".join(spaces)


_ASKED: dict[MatrixOp, str] = {
    "eigenvectors": "the eigenvectors of $A$ (its eigenspaces $E_{\\lambda}(A)$)",
    "diagonalize": "$P$ and $D$ with $A = PDP^{-1}$",
}


def _matrix(rows: list[list[float]]) -> Any:
    from sympy import Matrix, Rational

    return Matrix([[Rational(str(value)) for value in row] for row in rows])


def _term(value: Any) -> str:
    """A factor in a product: ``(-2)`` keeps its sign apart from the operation."""
    from sympy import latex

    return f"\\left({latex(value)}\\right)" if value < 0 else str(latex(value))


def _difference(a: Any, b: Any, c: Any, d: Any) -> str:
    """``ad - bc`` with every factor shown: ``2 \\cdot 3 - 1 \\cdot 5``."""
    return f"{_term(a)} \\cdot {_term(b)} - {_term(c)} \\cdot {_term(d)}"


def _determinant_lines(matrix: Any) -> tuple[str, ...]:
    """``ad - bc`` for a 2 by 2, the first-row expansion for a 3 by 3; each equal to the det."""
    from sympy import latex

    det = matrix.det()
    if matrix.rows == 2:
        (a, b), (c, d) = matrix.tolist()
        shown = _difference(a, d, b, c)
        if a * d - b * c == det:
            return (math_line(f"\\det(A) = {shown} = {latex(det)}", "$ad - bc$"),)
    if matrix.rows == 3:
        terms: list[str] = []
        total = 0
        for column in range(3):
            minor = matrix.minor_submatrix(0, column)
            (p, q), (r, s) = minor.tolist()
            entry = matrix[0, column]
            sign = "-" if column == 1 else "+"
            terms.append(f"{sign} {_term(entry)}\\left({_difference(p, s, q, r)}\\right)")
            total += (-1) ** column * entry * (p * s - q * r)
        if total == det:
            expansion = " ".join(terms).removeprefix("+ ")
            return (
                math_line(f"\\det(A) = {expansion} = {latex(det)}", "expand along the first row"),
            )
    return (math_line(f"\\det(A) = {latex(det)}"),)


def _inverse_lines(matrix: Any) -> tuple[str, ...] | None:
    """``A^{-1} = \\frac{1}{\\det(A)} \\operatorname{adj}(A)``, the product checked."""
    from sympy import latex

    det = matrix.det()
    if det == 0:
        return None
    adjugate = matrix.adjugate()
    inverse = matrix.inv()
    if adjugate / det != inverse or matrix * inverse != matrix.eye(matrix.rows):
        return None
    note = (
        "swap $a$ and $d$, change the signs of $b$ and $c$, divide by $\\det(A)$"
        if matrix.rows == 2
        else "the adjugate over the determinant"
    )
    # With a determinant of 1 the adjugate is the inverse: no ``\\frac{1}{1}`` to show.
    scaled = "" if det == 1 else f" = \\frac{{1}}{{{latex(det)}}}{latex(adjugate)}"
    return (
        math_line(
            rf"A^{{-1}} = \frac{{1}}{{\det(A)}}\operatorname{{adj}}(A){scaled}"
            f" = {latex(inverse)}",
            note,
        ),
    )


def _result(op: MatrixOp, rows: list[list[float]]) -> str | None:
    """The result's value as the card shows it, or None when there is none to show."""
    result = math_solve.compute_matrix(MatrixInput(operation=op, rows=rows))
    if op == "determinant":
        return result.determinant_latex
    if op == "inverse":
        return result.inverse_latex
    return result.result_latex


def multi_result_matrix_block(
    intent: MathIntent, ops: list[MatrixOp], lines: list[str]
) -> VerifiedMathBlock | None:
    """Every result ``ops`` lists for ``intent.matrix_rows``, worked, in one card."""
    from sympy import latex

    rows = intent.matrix_rows or []
    matrix = _matrix(rows)
    shown_matrix = latex(matrix)
    steps: list[str] = []
    card: list[str] = []
    for op in ops:
        if op == "inverse" and matrix.det() == 0:
            steps.append(text_line("Since $\\det(A) = 0$, $A$ has no inverse."))
            card.append("A^{-1}\\ \\text{does not exist}")
            continue
        try:
            value = _result(op, rows)
        except math_solve.SolveServiceError:
            if op != "diagonalize":
                raise
            steps.append(text_line("$A$ is not diagonalizable."))
            card.append("A\\ \\text{is not diagonalizable}")
            continue
        if value is None:
            return None
        named = _named_parts(op, value) if op in _SELF_NAMED else f"{_NAMES[op]} = {value}"
        if op == "determinant":
            steps.extend(_determinant_lines(matrix))
        elif op == "inverse":
            worked = _inverse_lines(matrix)
            if worked is None:
                return None
            steps.extend(worked)
        else:
            steps.append(math_line(named))
        card.append(named)
    lines.extend(card)  # the model's verified text names each result, "does not exist" too
    answer = ",\\quad ".join(card)
    block = finish_with_answer(lines, answer)
    direct = render_workout(
        Workout(
            given=(math_line(f"A = {shown_matrix}"),),
            find=tuple(
                text_line(_ASKED[op]) if op in _ASKED else math_line(_NAMES[op]) for op in ops
            ),
            steps=tuple(steps),
        ),
        answer,
    )
    if not _closed_request(intent._request_text):
        return block  # "… and tell me why": the model writes around the verified results
    return replace(block, direct_reply=direct)


def _closed_request(text: str | None) -> bool:
    """Whether the question asks for the listed results and nothing besides."""
    from app.modules.math.match.matrix_requests import without_matrix_cues
    from app.modules.math.tools.direct import leftover_non_math_request
    from app.modules.math.tools.lesson import strip_teaching_signals

    if not text:
        return False
    return not leftover_non_math_request(strip_teaching_signals(without_matrix_cues(text)))
