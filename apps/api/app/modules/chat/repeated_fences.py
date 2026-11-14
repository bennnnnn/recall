"""A picture the reply repeats word for word is shown once.

The textbook run (2026-11-13) got its pie chart twice, with "%timeout" between the copies: a
stray control token from the model, not words of the reply. The second copy goes, and a
model control token alone on its line between the two goes with it. Every other line stays,
whatever its script (a Chinese or a Russian line, a working line): a picture shown twice is
a smaller fault than a line of the reply lost.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.services.md_fence_scan import Fence, iter_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# Fences that draw something: a repeat of one is a second copy of the same picture.
_PICTURE_LANGS = frozenset(
    {
        "chart",
        "vega",
        "vega-lite",
        "plot",
        "graph",
        "geometry",
        "mermaid",
        "simulation",
        "smiles",
        "molecule",
        "molecule3d",
    }
)
# A model's control token alone on a line ("%timeout", "<|im_end|>", "</s>"): no word.
_CONTROL = re.compile(r"(?:%|<\|?/?)[\w|]+(?:\|?>)?")


def _key(text: str, fence: Fence) -> tuple[str, str]:
    return fence.lang.lower(), " ".join(text[fence.body_start : fence.body_end].split())


def _own_lines(gap: str) -> str:
    """The lines between two copies as written, any control token alone on a line left out."""
    lines = gap.split("\n")
    kept = "\n".join(line for line in lines if not _CONTROL.fullmatch(line.strip())).strip("\n ")
    return f"\n\n{kept}\n\n" if kept else "\n\n"


def drop_repeated_fences(text: str) -> str:
    fences = [fence for fence in iter_fences(text) if fence.closed]
    pictures = [fence for fence in fences if fence.lang.lower() in _PICTURE_LANGS]
    if len(pictures) < 2:
        return text
    seen: set[tuple[str, str]] = set()
    # (start, end) of each second copy, and of the gap before it when its twin is just above.
    repeats: list[tuple[int, int, int | None]] = []
    previous: Fence | None = None
    for fence in fences:
        key = _key(text, fence)
        if fence.lang.lower() in _PICTURE_LANGS and key in seen:
            twin = previous is not None and _key(text, previous) == key
            repeats.append((fence.start, fence.end, previous.end if twin and previous else None))
        seen.add(key)
        previous = fence
    for start, end, gap in reversed(repeats):
        if gap is None:
            text = text[:start].rstrip("\n ") + "\n" + text[end:].lstrip("\n")
        else:
            text = text[:gap].rstrip("\n ") + _own_lines(text[gap:start]) + text[end:].lstrip("\n")
    return text.rstrip() + "\n" if text.endswith("\n") else text.rstrip()


def drop_repeated_pictures(state: FinalizeState) -> str:
    """The finalize pass: the model's repeated pictures go; a server reply's pictures (one
    scene under each part) are its own."""
    if state.server_text:
        return state.text
    return drop_repeated_fences(state.text)
