"""The model's own ```simulation scene never ships: a scene is solver-sampled.

Moved out of ``services.answer_fence`` (the answer-card protocol): chat's finalize is its one
owner.
"""

from __future__ import annotations

import re

from app.services.answer_fence import normalize_owned_fences
from app.services.md_fence_scan import map_closed_fences

_DIAGRAM_FAIL_NOTE = "*Could not render that diagram.*"


def strip_model_simulation_fences(text: str) -> str:
    """A ```simulation scene is solver-sampled. The model's own never ships."""
    if "simulation" not in text.lower():
        return text
    normalized = normalize_owned_fences(text, ("simulation",))
    stripped = map_closed_fences(normalized, "simulation", lambda _body: "")
    if stripped == normalized:
        return text
    cleaned = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return cleaned or _DIAGRAM_FAIL_NOTE
