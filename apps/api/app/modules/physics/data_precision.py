"""The data's precision: the fewest significant figures among the values the solver read.

"Give the answer to the correct number of significant figures" asks the precision a class
grades: that of the measured values the answer is worked from. Only the values a solve bound
count, each as the question wrote it ("1.20 s" is three figures): a list's "1.", a part's
"Question 2", a count of resistors and a formula's "1/2" are no data, and read as data they
showed a checked 3.62 m/s as "4 m/s" (review of #2604).
"""

from __future__ import annotations

import math

from app.modules.physics.accounting import param_readings
from app.modules.physics.givens import scan_givens
from app.modules.physics.schemas import PhysicsIntent
from app.services.latex_markup import without_markup
from app.services.rounding_rule import written_figures


def bound_figures(intent: PhysicsIntent | None, question: str) -> int:
    """The fewest figures a measured value the solve read is written to, 0 for none."""
    if intent is None:
        return 0
    # The question as written: a reading normalizes "1.20 s" to "1.2 s" and loses a figure.
    text = without_markup(question)
    bound = [(dimension, si) for dimension, si in param_readings(intent) if si is not None]
    counts = []
    for given in scan_givens(text):
        if not given.unit or given.si is None:
            continue
        if not any(
            dimension == given.dimension
            and si is not None
            and given.si is not None
            and math.isclose(si, given.si, rel_tol=1e-9, abs_tol=1e-15)
            for dimension, si in bound
        ):
            continue
        figures = written_figures(text[given.start : given.end].replace(",", ""))
        if figures:
            counts.append(figures)
    return min(counts, default=0)
