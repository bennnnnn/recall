"""kind → verified system block. Registry: _BLOCK_BUILDERS."""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.core.config import Settings
from app.models.math_schemas import MathIntent
from app.services import math_service
from app.services.math_tools.block.algebra import (
    _verified_block_equation,
    _verified_block_inequality,
    _verified_block_numerical_method,
    _verified_block_system,
)
from app.services.math_tools.block.common import (
    VerifiedMathBlock as VerifiedMathBlock,
)
from app.services.math_tools.block.common import (
    _answer_canonical as _answer_canonical,
)
from app.services.math_tools.block.common import (
    _diagram_block as _diagram_block,
)
from app.services.math_tools.block.common import (
    _fence as _fence,
)
from app.services.math_tools.block.common import (
    _finish_with_answer as _finish_with_answer,
)
from app.services.math_tools.block.common import (
    _format_equation_answer as _format_equation_answer,
)
from app.services.math_tools.block.common import (
    _format_system_answer as _format_system_answer,
)
from app.services.math_tools.block.discrete import (
    _verified_block_calculus,
    _verified_block_combinatorics,
    _verified_block_limit,
    _verified_block_matrix,
    _verified_block_number_theory,
    _verified_block_series,
    _verified_block_statistics,
)
from app.services.math_tools.block.geometry import (
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
from app.services.math_tools.block.graph import (
    _verified_block_graph,
    _verified_block_graph_pair,
    _verified_block_point,
    _verified_block_vertical,
)

logger = logging.getLogger(__name__)

_BlockBuilder = Callable[[MathIntent, Settings, list[str]], VerifiedMathBlock | None]

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
}


def _build_verified_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    lines: list[str] = [
        "Symbolic math results (verified by SymPy — use these exact values in your answer):"
    ]

    try:
        builder = _BLOCK_BUILDERS.get(intent.kind)
        if builder is None:
            from app.services.math_tools.school import SCHOOL_BLOCK_BUILDERS

            builder = SCHOOL_BLOCK_BUILDERS.get(intent.kind)
        if builder is None:
            return None
        return builder(intent, settings, lines)
    except math_service.MathServiceError as exc:
        logger.info("math_tools skipped: %s", exc)
        return None
    except Exception:
        logger.exception("math_tools failed")
        return None
