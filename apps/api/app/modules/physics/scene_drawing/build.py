"""The scene a reply described, checked and drawn: one picture of the question's setup."""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.physics.fence import scene_fence
from app.modules.physics.field_lines.build import field_fences
from app.modules.physics.scene_drawing.apparatus import described_apparatus
from app.modules.physics.scene_drawing.describe import described_scene
from app.modules.physics.scene_drawing.motion_graph import described_motion


def scene_fences(
    descriptions: Sequence[str], texts: Sequence[str], asked: bool = True
) -> list[str]:
    """The pictures of the first described scene that checks against ``texts`` (the user's
    messages, the last first); none when none does. One setup, one scene: a question in
    parts gets one picture of what it is about. A motion's graphs only when the message
    asks to see a picture, as its contract is only then given (review)."""
    fences: list[str] = []
    for body in descriptions:
        specs = described_scene(body, texts) or described_apparatus(body, texts)
        if specs and not fences:
            fences = [
                scene_fence(spec.model_dump(mode="json", exclude_none=True)) for spec in specs
            ]
    # A motion's graphs beside its scene: the first description of them that checks.
    described = (described_motion(body, texts) for body in descriptions) if asked else iter(())
    graphs = next((g for g in described if g), [])
    return [*fences, *(scene_fence(g.model_dump(mode="json", exclude_none=True)) for g in graphs)]


def physics_fences(
    descriptions: Sequence[str],
    texts: Sequence[str],
    problem: str | None = None,
    asked: bool = True,
) -> list[str]:
    """Every picture a physics reply described: its field pictures, read from the user's
    own lines (the parts, plates and charges of "Draw the field lines around: a) ..."),
    only when the message asks to see one; then its scene, of the problem a follow-up
    points back to when there is one."""
    scene_texts = [problem, *texts] if problem else list(texts)
    fields = field_fences(descriptions, texts) if asked else []
    return [*fields, *scene_fences(descriptions, scene_texts, asked)]
