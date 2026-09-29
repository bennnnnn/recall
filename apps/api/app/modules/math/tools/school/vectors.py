"""Vector extractor and verified block."""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.modules.math import school as math_school
from app.modules.math.match.coordinate_vector import literal_math_tuples
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer


def _extract_vector_intent(cleaned: str) -> MathIntent | None:
    from app.modules.math.tools.extractors.formulas import extract_vector_formulas

    extra = extract_vector_formulas(cleaned)
    if extra is not None:
        return extra
    lower = cleaned.lower()
    op: str | None = None
    if "cross" in lower:
        op = "cross"
    elif "dot" in lower:
        op = "dot"
    elif "magnitude" in lower or "norm of" in lower:
        op = "magnitude"
    if op is None:
        return None
    vecs = _angle_vectors(cleaned)
    if not vecs:
        return None
    if op == "magnitude":
        if len(vecs) != 1:
            return None
        return MathIntent(kind="vector", school_op=op, vec_a=vecs[0], operation="solve")
    if len(vecs) != 2 or len(vecs[0]) != len(vecs[1]):
        return None
    return MathIntent(kind="vector", school_op=op, vec_a=vecs[0], vec_b=vecs[1], operation="solve")


def _angle_vectors(text: str) -> list[list[float]]:
    return literal_math_tuples(text, "<", ">") or []


def _verified_block_vector(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.vec_a:
        return None
    if intent.school_op == "magnitude":
        answer = math_school.vector_magnitude(intent.vec_a)
    elif intent.school_op == "unit":
        from app.modules.math import formulas as math_formulas

        answer = math_formulas.vector_unit(intent.vec_a)
    elif intent.school_op == "dot" and intent.vec_b:
        answer = math_school.vector_dot(intent.vec_a, intent.vec_b)
    elif intent.school_op == "cross" and intent.vec_b:
        answer = math_school.vector_cross(intent.vec_a, intent.vec_b)
    elif intent.school_op == "angle" and intent.vec_b:
        from app.modules.math import formulas as math_formulas

        answer = math_formulas.vector_angle_degrees(intent.vec_a, intent.vec_b)
    elif intent.school_op == "projection" and intent.vec_b:
        from app.modules.math import formulas as math_formulas

        answer = math_formulas.vector_projection(intent.vec_a, intent.vec_b)
    else:
        return None
    lines.append(f"{intent.school_op}: {answer}")
    return _finish_with_answer(lines, answer)
