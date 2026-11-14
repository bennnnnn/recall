"""Where a LaTeX ``{…}`` group ends: one brace matcher for every reader of a reply's or a
keyboard's TeX (the times sign, physics notation, keyboard fractions, a worked block's word
groups)."""

from __future__ import annotations

import re
from collections.abc import Callable


def group_end(latex: str, brace: int) -> int:
    """Past the ``{…}`` group that opens at ``brace``; the text's end when it never closes."""
    return closed_group_end(latex, brace) or len(latex)


def closed_group_end(latex: str, brace: int) -> int | None:
    """Past the ``{…}`` group that opens at ``brace``; None when no group opens there or
    it never closes."""
    if brace >= len(latex) or latex[brace] != "{":
        return None
    depth = 0
    for index in range(brace, len(latex)):
        if latex[index] == "{":
            depth += 1
        elif latex[index] == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def map_groups(
    latex: str,
    opener: re.Pattern[str],
    outside: Callable[[str], str],
    inside: Callable[[re.Match[str], str], str],
) -> str:
    """``latex`` with ``outside`` applied to the text between the groups ``opener`` opens
    (its match ends on the group's ``{``) and each whole group replaced by ``inside``, given
    the opener and the group's text. A group that never closes, and all after it, is
    outside."""
    out: list[str] = []
    at = 0
    for opened in opener.finditer(latex):
        if opened.start() < at:
            continue  # inside a group already mapped
        end = closed_group_end(latex, opened.end() - 1)
        if end is None:
            break
        out.append(outside(latex[at : opened.start()]))
        out.append(inside(opened, latex[opened.end() : end - 1]))
        at = end
    out.append(outside(latex[at:]))
    return "".join(out)
