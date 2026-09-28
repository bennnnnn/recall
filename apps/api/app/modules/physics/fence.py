"""Physics-owned reconciliation of answer, trajectory, and simulation fences."""

from __future__ import annotations

import json
import re

from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES
from app.services.md_fence_scan import close_unclosed_fences, strip_closed_fences
from app.services.solving import VerifiedPhysicsBlock


def _canonical_specs(verified: VerifiedPhysicsBlock) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for spec in (verified.canonical_fence, *verified.canonical_fences):
        if spec is not None and spec not in specs:
            specs.append(spec)
    return specs


def validate_physics_fences(
    content: str,
    *,
    verified: VerifiedPhysicsBlock | None = None,
) -> str:
    """Drop model-authored result fences and append only solver-owned data."""
    had_visual_fence = any(
        f"```{language}" in content for language in ("graph", "simulation", "geometry")
    )
    cleaned = content
    for language in ("answer", "result", "final", "graph", "simulation", "geometry"):
        cleaned = strip_closed_fences(cleaned, language)
    cleaned = cleaned.strip()
    if verified is None:
        if had_visual_fence and not cleaned:
            return "*Could not render that diagram.*"
        return cleaned
    extras: list[str] = []
    answer = (verified.display_answer or verified.canonical_answer or "").strip()
    if answer and any(line.rstrip("*_`~ \t").endswith("?") for line in cleaned.splitlines()):
        normalized_content = re.sub(r"\s+", " ", cleaned.lower())
        normalized_answer = re.sub(r"\s+", " ", answer.lower())
        if normalized_answer not in normalized_content:
            return cleaned
    if answer:
        extras.append(f"```answer\n{answer}\n```")
    for spec in _canonical_specs(verified):
        spec_type = spec.get("type")
        if spec_type == "answer":
            continue
        language = "simulation" if spec_type in SIMULATION_SPEC_TYPES else "graph"
        extras.append(f"```{language}\n{json.dumps(spec, separators=(',', ':'))}\n```")
    return "\n\n".join(part for part in (cleaned, *extras) if part).strip()


def replace_unclosed_physics_fences_safe(
    content: str,
    verified: VerifiedPhysicsBlock | None,
) -> str:
    """Physics-owned, no-solver fallback after finalization fails.

    Close a truncated rich fence, then make one ordinary canonical pass.  If
    even that fails, strip every physics/result fence and keep only prose;
    never send a physics turn through math's graph recovery semantics.
    """
    closed = close_unclosed_fences(content)
    try:
        return validate_physics_fences(closed, verified=verified)
    except Exception:
        cleaned = closed
        had_visual = any(
            f"```{language}" in cleaned for language in ("graph", "simulation", "geometry")
        )
        for language in ("answer", "result", "final", "graph", "simulation", "geometry"):
            cleaned = strip_closed_fences(cleaned, language)
        cleaned = cleaned.strip()
        return cleaned or ("*Could not render that diagram.*" if had_visual else "")


def needs_physics_fence_validate(
    content: str,
    verified: VerifiedPhysicsBlock | None,
) -> bool:
    return verified is not None or any(
        f"```{language}" in content
        for language in ("answer", "result", "final", "graph", "simulation", "geometry")
    )
