"""Options a, b, c listed in order: a multiple-choice question."""

from __future__ import annotations

import re

# "a) …", "(b) …", "C. …", "[D] …": an option's letter, after a space or the start.
_OPTION = re.compile(r"(?:^|(?<=[\s\[(]))\(?([a-dA-D])[).\]]\s+\S")


def lists_choices(text: str) -> bool:
    """``text`` offers options a, b and c (and maybe d), in that order."""
    return "abc" in "".join(match.group(1).lower() for match in _OPTION.finditer(text))
