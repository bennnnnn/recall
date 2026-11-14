"""A drawn structure's caption as the phone reads one, and the structure without it.

The phone draws a ```smiles or ```chemistry fence's last SMILES line and captions it with the
lines above (``apps/mobile/lib/chemistry/fence.ts``: ``parseChemistryFence``, ``readSmiles``).
Only the chemistry pass holds a caption's name to its structure (``chemistry.caption_names``).
Where it cannot (it failed, chemistry is off, the reply was stopped or fell back, a fence past
its cap), the caption goes and the structure stays: a model's "Caffeine" over ethanol's
SMILES shipped as written (review, 2026-11-13).
"""

from __future__ import annotations

import re

from app.services.md_fence_scan import iter_closed_fences

STRUCTURE_LANGS = ("smiles", "chemistry")
# The phone's SMILES line: its characters and its limit (``readSmiles``).
_SMILES_LINE = re.compile(r"[A-Za-z0-9@+\-\[\]()=#$/:\\.>%!~,*]+")
_SMILES_LABEL = re.compile(r"^smiles:\s*", re.IGNORECASE)
_MAX_SMILES_CHARS = 500
_UNDRAWN = "*Could not render that structure.*\n"


def _lines(body: str) -> list[str]:
    """The fence's lines the phone reads: trimmed, no blank one, no ``#`` comment."""
    return [
        line.strip()
        for line in body.split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]


def drawn_line(body: str) -> str | None:
    """The line the phone draws: the last that is a SMILES; None when none is."""
    for line in reversed(_lines(body)):
        raw = _SMILES_LABEL.sub("", line, count=1).strip()
        if raw and len(raw) <= _MAX_SMILES_CHARS and _SMILES_LINE.fullmatch(raw):
            return line
    return None


def uncaptioned_fence(lang: str, body: str) -> str:
    """A closed ``lang`` fence as its structure alone, its closer's line break included."""
    line = drawn_line(body)
    return f"```{lang}\n{line}\n```\n" if line is not None else _UNDRAWN


def without_structure_captions(text: str) -> str:
    """``text`` with every closed structure fence's caption gone, its structure kept; a fence
    with no caption stays as written."""
    lower = text.lower()
    for lang in STRUCTURE_LANGS:
        if lang not in lower:
            continue
        pieces: list[str] = []
        cursor = 0
        for start, end, body in iter_closed_fences(text, lang):
            line = drawn_line(body)
            if line is not None and _lines(body) == [line]:
                continue
            pieces += [text[cursor:start], uncaptioned_fence(lang, body)]
            cursor = end
        if pieces:
            text = "".join(pieces) + text[cursor:]
    return text
