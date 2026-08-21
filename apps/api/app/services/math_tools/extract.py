"""Ordered MathIntent extraction behind the stable public seam."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from app.models.math_schemas import MathIntent
from app.services.math_tools.extractors.algebra import (
    ALGEBRA_EXTRACTORS,
    PRE_DISCRETE_ALGEBRA_EXTRACTORS,
)
from app.services.math_tools.extractors.calculus import CALCULUS_EXTRACTORS
from app.services.math_tools.extractors.discrete_statistics import (
    DISCRETE_STATISTICS_EXTRACTORS,
)
from app.services.math_tools.extractors.geometry_graph import (
    GEOMETRY_GRAPH_EXTRACTORS,
    SOLID_EXTRACTOR,
)
from app.services.math_tools.physics import PHYSICS_EXTRACTORS
from app.services.math_tools.school import SCHOOL_EXTRACTORS

_INTENT_EXTRACTORS: Sequence[Callable[[str], MathIntent | None]] = (
    SOLID_EXTRACTOR,
    *SCHOOL_EXTRACTORS,
    *PHYSICS_EXTRACTORS,
    *GEOMETRY_GRAPH_EXTRACTORS,
    *CALCULUS_EXTRACTORS,
    *PRE_DISCRETE_ALGEBRA_EXTRACTORS,
    *DISCRETE_STATISTICS_EXTRACTORS,
    *ALGEBRA_EXTRACTORS,
)

_ROOTS_RE = re.compile(r"\b(?:find(?:\s+the)?\s+)?(?:roots|zeros)\s+of\s+(.+)", re.IGNORECASE)


def extract_math_intent(text: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    cleaned = mtm.prepare(text)
    if not cleaned:
        return None
    roots_match = _ROOTS_RE.search(cleaned)
    if roots_match:
        tail = roots_match.group(1).strip()
        if "=" not in tail and any(c.isdigit() for c in tail):
            cleaned = f"solve {tail} = 0"
    for extractor in _INTENT_EXTRACTORS:
        intent = extractor(cleaned)
        if intent is not None:
            return intent
    return None
