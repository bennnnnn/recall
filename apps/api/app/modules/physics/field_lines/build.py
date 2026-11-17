"""The field pictures a reply described, checked and drawn: one fence per block that holds."""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.physics.field_lines.describe import read_description
from app.modules.physics.field_lines.picture import field_fence

# Most pictures one reply draws: a question in parts asks for one each.
_MOST = 4


def field_fences(descriptions: Sequence[str], texts: Sequence[str]) -> list[str]:
    """Each described picture that checks against ``texts`` (the user's messages), in the
    reply's order; one that does not is left out. Two blocks that describe the same picture
    draw it once."""
    fences: list[str] = []
    for body in descriptions:
        picture = read_description(body, texts)
        fence = field_fence(picture) if picture is not None else None
        if fence is not None and fence not in fences:
            fences.append(fence)
        if len(fences) == _MOST:
            break
    return fences
