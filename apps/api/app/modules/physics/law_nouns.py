"""The noun a law is asked for its result with: "range", "work done", "density".

A law's asks are the phrases a question names its result by; some are questions or verbs
("how far", "accelerate"). The first that is a noun names the quantity on a reply's lines.
"""

from __future__ import annotations

import re

from app.services.law_binding.spec import FormulaSpec

# An ask that is a question or a verb phrase, not the quantity's name: "how far", "reach the
# top", "accelerate".
_NOT_A_NOUN = re.compile(
    r"^(?:how|what|which|when|where|why|is|are|does|do|can|reach|hit|stop|take|land|"
    r"accelerate|fall|rise|travel|weigh)\b",
    re.IGNORECASE,
)


def asked_noun(spec: FormulaSpec) -> str | None:
    """The noun the law is asked for its result with ("work done", "density"), if any."""
    if spec.binding is None:
        return None
    for ask in spec.binding.asks:
        if not _NOT_A_NOUN.match(ask.strip()):
            return ask.strip()
    return None
