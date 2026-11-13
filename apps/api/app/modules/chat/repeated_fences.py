"""A picture the reply repeats word for word is shown once.

The textbook run (2026-11-13) got its pie chart twice, with "%timeout" and a line of
Arabic and Chinese characters between the copies: stray tokens from the model, not words
of the reply. The second copy goes. A line between two copies goes with it only when it is
clearly junk: a control token alone on its line, or letters of a script written nowhere
else in the reply or the question, and no maths. Anything else stays, a working line, a heading or a sentence in any language: a
picture shown twice is a smaller fault than a step of the working lost.
"""

from __future__ import annotations

import re
import unicodedata
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
# Maths in a line: a digit, a relation or an operation, a Greek letter (θ, π).
_MATHS = re.compile("[0-9=<>+\u2212\u00d7\u00f7^\u221a\u00b0\u0370-\u03ff]")
# A model's control token alone on a line ("%timeout", "<|im_end|>", "</s>"): no word.
_CONTROL = re.compile(r"(?:%|<\|?/?)[\w|]+(?:\|?>)?")
# Scripts one language writes together: Japanese mixes kana and kanji.
_FAMILIES = {"HIRAGANA": "CJK", "KATAKANA": "CJK", "HALFWIDTH": "CJK", "FULLWIDTH": "CJK"}


def _script(char: str) -> str:
    """The script a letter is written in, by its Unicode name ("LATIN", "ARABIC", "CJK")."""
    try:
        name = unicodedata.name(char).split(" ")[0]
    except ValueError:
        return ""
    return _FAMILIES.get(name, name)


def _junk(line: str, known: set[str]) -> bool:
    """Clearly not the reply's words: a control token alone on its line, or letters of a
    script written nowhere else in the reply or the question, and no maths. A working line ("A = 6 cm²", "x = 5" in an Amharic
    reply), a heading or a sentence stays."""
    letters = [c for c in line if c.isalpha()]
    if not letters or _MATHS.search(line):
        return False
    return _CONTROL.fullmatch(line.strip()) is not None or any(
        _script(c) not in known for c in letters
    )


def _key(text: str, fence: Fence) -> tuple[str, str]:
    return fence.lang.lower(), " ".join(text[fence.body_start : fence.body_end].split())


def _own_lines(gap: str, known: set[str]) -> str:
    """The lines between two copies as written, the junk left out."""
    kept = "\n".join(line for line in gap.split("\n") if not _junk(line, known)).strip("\n ")
    return f"\n\n{kept}\n\n" if kept else "\n\n"


def _known_scripts(
    text: str, fences: list[Fence], gaps: list[tuple[int, int]], question: str
) -> set[str]:
    """The scripts the reply's prose (outside its pictures and the gaps judged) and the
    question are written in."""
    skipped = sorted([(f.start, f.end) for f in fences] + gaps)
    prose, last = [question], 0
    for start, end in skipped:
        prose.append(text[last:start])
        last = max(last, end)
    prose.append(text[last:])
    return {_script(c) for c in "".join(prose) if c.isalpha()}


def drop_repeated_fences(text: str, question: str = "") -> str:
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
    gaps = [(gap, start) for start, _, gap in repeats if gap is not None]
    known = _known_scripts(text, fences, gaps, question)
    for start, end, gap in reversed(repeats):
        if gap is None:
            text = text[:start].rstrip("\n ") + "\n" + text[end:].lstrip("\n")
        else:
            kept = _own_lines(text[gap:start], known)
            text = text[:gap].rstrip("\n ") + kept + text[end:].lstrip("\n")
    return text.rstrip() + "\n" if text.endswith("\n") else text.rstrip()


def drop_repeated_pictures(state: FinalizeState) -> str:
    """The finalize pass: the model's repeated pictures go; a server reply's pictures (one
    scene under each part) are its own."""
    if state.server_text:
        return state.text
    return drop_repeated_fences(state.text, state.ctx.user_message_content or "")
