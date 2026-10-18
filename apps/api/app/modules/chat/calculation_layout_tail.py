"""How a laid-out line ends: its note and its hard break (twin: calculationLayoutTail.ts)."""

from __future__ import annotations


def finish_inline(parts: list[str], tail: str) -> str:
    """The laid-out rows of a line, then whatever followed the maths.

    "$h = …, k = …$ — Vertex of a parabola": the note names the first row, not a
    line of its own. The line's hard break ("…$  ") still ends it, or the next
    line runs on.
    """
    note = tail.strip()
    if parts and note.startswith("\u2014 ") and "\n" in parts[-1]:
        first, _, rest = parts[-1].partition("\n")
        parts[-1] = f"{first.rstrip()} {note}  \n{rest}"
    elif note:
        parts.append(tail.lstrip() if parts else tail)
    return keep_hard_break(tail, "\n".join(parts))


def keep_hard_break(original: str, laid: str) -> str:
    """``laid`` ends with ``original``'s hard break, if it had one."""
    return f"{laid.rstrip()}  " if original.endswith("  ") else laid
