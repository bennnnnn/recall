"""The scene a reply described, checked and drawn: one picture of the question's setup."""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.physics.fence import scene_fence
from app.modules.physics.field_lines.build import field_fences
from app.modules.physics.scene_drawing.describe import described_scene


def scene_fences(descriptions: Sequence[str], texts: Sequence[str]) -> list[str]:
    """The pictures of the first described scene that checks against ``texts`` (the user's
    messages, the last first); none when none does. One setup, one scene: a question in
    parts gets one picture of what it is about."""
    for body in descriptions:
        specs = described_scene(body, texts)
        if specs:
            return [scene_fence(spec.model_dump(mode="json", exclude_none=True)) for spec in specs]
    return []


def physics_fences(
    descriptions: Sequence[str], texts: Sequence[str], problem: str | None = None
) -> list[str]:
    """Every picture a physics reply described: its field pictures, read from the user's
    own lines (the parts, plates and charges of "Draw the field lines around: a) ..."),
    then its scene, of the problem a follow-up points back to when there is one."""
    scene_texts = [problem, *texts] if problem else list(texts)
    return [*field_fences(descriptions, texts), *scene_fences(descriptions, scene_texts)]
