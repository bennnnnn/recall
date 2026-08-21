"""Discrete-math and statistics intent extractors."""

from __future__ import annotations

from app.models.math_schemas import MathIntent


def _extract_statistics_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    signal = mtm.stats_signal(cleaned)
    if signal is None:
        return None
    op, numbers = signal
    return MathIntent(kind="statistics", stats_op=op, stats_numbers=numbers, operation="solve")


def _extract_combinatorics_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    signal = mtm.combinatorics_signal(cleaned)
    if signal is None:
        return None
    op, n, k = signal
    return MathIntent(kind="combinatorics", combo_op=op, combo_n=n, combo_k=k, operation="solve")


def _extract_number_theory_intent(cleaned: str) -> MathIntent | None:
    from app.services import math_text_match as mtm

    signal = mtm.number_theory_signal(cleaned)
    if signal is None:
        return None
    op, a, b = signal
    return MathIntent(
        kind="number_theory", numtheory_op=op, numtheory_a=a, numtheory_b=b, operation="solve"
    )


DISCRETE_STATISTICS_EXTRACTORS = (
    _extract_statistics_intent,
    _extract_combinatorics_intent,
    _extract_number_theory_intent,
)
