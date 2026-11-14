"""The model's own scenes and structures never ship: only the server draws them.

A ```simulation scene is solver-sampled; a ```chem_scene, ```molecule or ```molecule3d is
drawn from a chemistry solve, RDKit or PubChem (``answer_fence.SERVER_DRAWN_LANGS``). Moved
out of ``services.answer_fence`` (the answer-card protocol): chat's finalize is its one owner.
"""

from __future__ import annotations

import re

from app.services.answer_fence import SERVER_DRAWN_LANGS, normalize_owned_fences
from app.services.md_fence_scan import map_closed_fences

_DIAGRAM_FAIL_NOTE = "*Could not render that diagram.*"


def strip_model_drawn_fences(text: str, langs: tuple[str, ...] = SERVER_DRAWN_LANGS) -> str:
    """``text`` without the server-drawn fences of ``langs`` a model wrote, in any spelling.

    Every turn's chemistry pass and SMILES drawing run later and add the server's own.
    """
    lower = text.lower()
    if not any(lang in lower for lang in langs):
        return text
    normalized = normalize_owned_fences(text, langs)
    stripped = normalized
    for lang in langs:
        stripped = map_closed_fences(stripped, lang, lambda _body: "")
    if stripped == normalized:
        return text
    cleaned = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return cleaned or _DIAGRAM_FAIL_NOTE
