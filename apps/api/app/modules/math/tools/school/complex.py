"""Complex-number extractor and verified block."""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.modules.math import match as mtm
from app.modules.math import school as math_school
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer


def _extract_complex_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    from app.modules.math.tools.extractors.formulas import extract_complex_op

    op = extract_complex_op(cleaned)
    if op is None:
        has_complex_token = "complex" in lower or "i)" in lower or "+ i" in lower or "- i" in lower
        if not has_complex_token and "imaginary" not in lower:
            return None
    if mtm.has_equation(cleaned) and "solve" in lower:
        return None
    expr = cleaned.strip()
    while True:
        for prefix in (
            "simplify",
            "evaluate",
            "compute",
            "modulus of",
            "modulus",
            "magnitude of",
            "magnitude",
            "argument of",
            "argument",
            "arg of",
            "conjugate of",
            "conjugate",
            "polar form of",
            "polar form",
            "polar of",
            "complex",
        ):
            if expr.lower().startswith(prefix + " "):
                expr = expr[len(prefix) :].lstrip()
                break
        else:
            break
    return MathIntent(kind="complex", school_op=op or "eval", expr=expr, operation="solve")


def _verified_block_complex(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.expr:
        return None
    from app.modules.math import formulas as math_formulas

    if intent.school_op == "modulus":
        answer = math_formulas.complex_modulus(intent.expr)
    elif intent.school_op == "argument":
        answer = math_formulas.complex_argument(intent.expr)
    elif intent.school_op == "conjugate":
        answer = math_formulas.complex_conjugate(intent.expr)
    elif intent.school_op == "polar":
        answer = math_formulas.complex_polar(intent.expr)
    else:
        answer = math_school.evaluate_complex(intent.expr)
    lines.append(f"Result: {answer}")
    return _finish_with_answer(lines, answer)
