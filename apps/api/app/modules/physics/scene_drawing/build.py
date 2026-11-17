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
            return [scene_fence(spec.model_dump(mode="json")) for spec in specs]
    return []


def physics_fences(descriptions: Sequence[str], texts: Sequence[str]) -> list[str]:
    """Every picture a physics reply described: its field pictures, then its scene."""
    return [*field_fences(descriptions, texts), *scene_fences(descriptions, texts)]
