"""A picture the reply repeats word for word is shown once.

The textbook run (2026-11-13) got its pie chart twice, with "%timeout" and a line of
Arabic and Chinese characters between the copies: stray tokens from the model, not words
of the reply. The second copy goes. The lines between two copies go with it only when they
are not the reply's own words: a line with letters of a script the reply is not written in,
or with fewer than two words in the reply's script. A sentence between the copies stays.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from app.services.md_fence_scan import Fence, iter_fences

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
_WORD = re.compile(r"[^\W\d_]{2,}")
# Words in the reply's script a line between two copies needs to be the reply's own.
_OWN_WORDS = 2


def _script(char: str) -> str:
    """The script a letter is written in, by its Unicode name ("LATIN", "ARABIC", "CJK")."""
    try:
        return unicodedata.name(char).split(" ")[0]
    except ValueError:
        return ""


def _main_script(text: str, fences: list[Fence], question: str) -> str:
    """The script most of the reply's prose and the user's message are written in: a reply
    that is all pictures has only the stray lines for prose."""
    prose = [question]
    last = 0
    for fence in fences:
        prose.append(text[last : fence.start])
        last = fence.end
    prose.append(text[last:])
    counts = Counter(_script(c) for c in "".join(prose) if c.isalpha())
    return counts.most_common(1)[0][0] if counts else "LATIN"


def _stray(line: str, script: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    if any(_script(c) != script for c in letters):
        return True
    return len(_WORD.findall(line)) < _OWN_WORDS


def _key(text: str, fence: Fence) -> tuple[str, str]:
    return fence.lang.lower(), " ".join(text[fence.body_start : fence.body_end].split())


def _own_lines(gap: str, script: str) -> str:
    """The lines between two copies that are the reply's own words."""
    kept = [line for line in gap.split("\n") if line.strip() and not _stray(line, script)]
    return "\n\n" + "\n".join(kept) + "\n\n" if kept else "\n\n"


def drop_repeated_fences(text: str, question: str = "") -> str:
    fences = [fence for fence in iter_fences(text) if fence.closed]
    pictures = [fence for fence in fences if fence.lang.lower() in _PICTURE_LANGS]
    if len(pictures) < 2:
        return text
    script = _main_script(text, fences, question)
    seen: set[tuple[str, str]] = set()
    # (start, end, what stands in their place)
    cuts: list[tuple[int, int, str]] = []
    previous: Fence | None = None
    for fence in fences:
        key = _key(text, fence)
        if fence.lang.lower() in _PICTURE_LANGS and key in seen:
            if previous is not None and _key(text, previous) == key:
                gap = text[previous.end : fence.start]
                cuts.append((previous.end, fence.end, _own_lines(gap, script)))
            else:
                cuts.append((fence.start, fence.end, "\n"))
        seen.add(key)
        previous = fence
    for start, end, kept in reversed(cuts):
        text = text[:start].rstrip("\n ") + kept + text[end:].lstrip("\n")
    return text.rstrip() + "\n" if text.endswith("\n") else text.rstrip()
