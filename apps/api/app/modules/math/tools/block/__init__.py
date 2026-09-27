"""kind → verified system block. Registry: _BLOCK_BUILDERS."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.modules.math import solve as math_solve
from app.modules.math.tools.block.algebra import (
    _verified_block_equation,
    _verified_block_inequality,
    _verified_block_numerical_method,
    _verified_block_system,
)
from app.modules.math.tools.block.common import (
    _format_equation_answer as _format_equation_answer,
)
from app.modules.math.tools.block.common import (
    _format_system_answer as _format_system_answer,
)
from app.modules.math.tools.block.discrete import (
    _verified_block_calculus,
    _verified_block_combinatorics,
    _verified_block_limit,
    _verified_block_matrix,
    _verified_block_number_theory,
    _verified_block_series,
    _verified_block_statistics,
)
from app.modules.math.tools.block.geometry import (
    _verified_block_circle,
    _verified_block_parallelogram,
    _verified_block_rectangle,
    _verified_block_right_triangle,
    _verified_block_sector,
    _verified_block_solid,
    _verified_block_square,
    _verified_block_trapezoid,
    _verified_block_triangle,
    _verified_block_triangle_sides,
)
from app.modules.math.tools.block.graph import (
    _verified_block_graph,
    _verified_block_graph_pair,
    _verified_block_point,
    _verified_block_vertical,
)
from app.modules.math.tools.block.word import _verified_block_word_problem
from app.modules.math.tools.block.work import _verified_block_work_check
from app.services.solving import (
    VerifiedMathBlock as VerifiedMathBlock,
)
from app.services.solving import (
    _answer_canonical as _answer_canonical,
)
from app.services.solving import (
    _diagram_block as _diagram_block,
)
from app.services.solving import (
    _finish_with_answer as _finish_with_answer,
)

logger = logging.getLogger(__name__)

# ``Any`` is limited to this declarative registry boundary. Every concrete
# builder and the public dispatcher remain math-only and precisely typed.
_BlockBuilder = Callable[[Any, Settings, list[str]], VerifiedMathBlock | None]

_BLOCK_BUILDERS: dict[str, _BlockBuilder] = {
    "equation": _verified_block_equation,
    "inequality": _verified_block_inequality,
    "system": _verified_block_system,
    "numerical_method": _verified_block_numerical_method,
    "rectangle": _verified_block_rectangle,
    "square": _verified_block_square,
    "solid": _verified_block_solid,
    "circle": _verified_block_circle,
    "triangle": _verified_block_triangle,
    "right_triangle": _verified_block_right_triangle,
    "triangle_sides": _verified_block_triangle_sides,
    "trapezoid": _verified_block_trapezoid,
    "parallelogram": _verified_block_parallelogram,
    "sector": _verified_block_sector,
    "point": _verified_block_point,
    "vertical": _verified_block_vertical,
    "graph": _verified_block_graph,
    "graph_pair": _verified_block_graph_pair,
    "calculus": _verified_block_calculus,
    "limit": _verified_block_limit,
    "series": _verified_block_series,
    "statistics": _verified_block_statistics,
    "combinatorics": _verified_block_combinatorics,
    "number_theory": _verified_block_number_theory,
    "matrix": _verified_block_matrix,
    "work_check": _verified_block_work_check,
    "word_problem": _verified_block_word_problem,
}


def _build_verified_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    lines: list[str] = []

    try:
        builder: _BlockBuilder | None = _BLOCK_BUILDERS.get(intent.kind)
        if builder is None:
            from app.modules.math.tools.school import SCHOOL_BLOCK_BUILDERS

            builder = SCHOOL_BLOCK_BUILDERS.get(intent.kind)
        if builder is None:
            return None
        block = builder(intent, settings, lines)
        if block is None:
            return None
        from app.services.solving import wrap_verified_math

        return replace(
            block,
            text=wrap_verified_math(block.text),
            direct_request_text=(
                intent._request_text if block.direct_reply is not None else None
            ),
            direct_requires_calculus_guard=bool(
                block.direct_reply is not None
                and intent.kind == "calculus"
                and intent.school_op is None
                and intent.operation in {"differentiate", "integrate"}
            ),
            direct_answer_binding=(
                block.canonical_answer if block.direct_reply is not None else None
            ),
        )
    except math_solve.MathServiceError as exc:
        logger.info("math_tools skipped: %s", exc)
        return None
    except Exception:
        logger.exception("math_tools failed")
        return None
