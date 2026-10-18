"""Each subject's prompt hints, listed explicitly. The subject owns them; chat states them.

A subject's public file exposes ``<subject>_prompt_hints(short)`` and its reply policy.
Statistics and biology have no module yet: chat's ``continuation_subject`` names them,
so their one hint each stays in ``prompt_constants/format.py`` until a module owns it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.modules.chat.prompt_constants import (
    BIOLOGY_PRESENTATION_HINT,
    MATH_FENCE_SAFETY_HINT,
    STATISTICS_PRESENTATION_HINT,
    VERIFIED_SOLVE_SAFETY_HINT,
)
from app.modules.chemistry.reply_policy import chemistry_prompt_hints
from app.modules.math.reply_policy import MATH_REPLY_POLICY, math_prompt_hints
from app.modules.physics import PHYSICS_REPLY_POLICY, physics_prompt_hints


@dataclass(frozen=True)
class SubjectHints:
    """One subject's hints, and where the prompt states them."""

    # Short style or a compact turn -> the hints after the layout and photo hints.
    presentation: Callable[[bool], Sequence[str]]
    # The reply policy, after the shared copy and writing rules.
    closing: tuple[str, ...] = ()
    # The maths and physics packs carry their own maths-ink rules; the rest get chat's.
    shared_math_ink: bool = True


SUBJECT_HINTS: dict[str, SubjectHints] = {
    "physics": SubjectHints(physics_prompt_hints, (PHYSICS_REPLY_POLICY,), shared_math_ink=False),
    "math": SubjectHints(math_prompt_hints, (MATH_REPLY_POLICY,), shared_math_ink=False),
    "chemistry": SubjectHints(chemistry_prompt_hints),
    "statistics": SubjectHints(lambda _short: (STATISTICS_PRESENTATION_HINT,)),
    "biology": SubjectHints(lambda _short: (BIOLOGY_PRESENTATION_HINT,)),
}


def subject_presentation_hints(subject: str | None, *, short: bool) -> list[str]:
    """A subject's hints after the shared verified-solve rule; no subject gets maths ink."""
    hints = SUBJECT_HINTS.get(subject or "")
    if hints is None:
        return [MATH_FENCE_SAFETY_HINT]
    ink = [MATH_FENCE_SAFETY_HINT] if hints.shared_math_ink else []
    return [VERIFIED_SOLVE_SAFETY_HINT, *hints.presentation(short), *ink]


def subject_closing_hints(subject: str | None) -> tuple[str, ...]:
    """A subject's reply policy. It comes late, so the detail it allows wins."""
    hints = SUBJECT_HINTS.get(subject or "")
    return hints.closing if hints else ()
