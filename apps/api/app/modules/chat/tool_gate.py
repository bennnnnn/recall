"""Eligibility shared by prompt prefetch and the final tool-loop gate."""

from app.core.config import Settings
from app.models.orm import User


def should_classify_tool_web_search(
    content: str,
    settings: Settings,
    *,
    lightweight: bool,
    has_instant_reply: bool,
    has_verified_math: bool,
    has_search_sources: bool,
    user: User | None,
) -> bool:
    """Classify only if a web verdict can change an otherwise negative gate.

    Asking the actual gate preserves its image, math, feature and turn-mode
    rules rather than maintaining another list of intent heuristics.
    """
    if not settings.web_search_enabled or has_search_sources:
        return False
    from app.services.tool_loop import turn_needs_tool_loop

    flags = {
        "lightweight": lightweight,
        "has_instant_reply": has_instant_reply,
        "has_verified_math": has_verified_math,
        "has_search_sources": has_search_sources,
    }
    return not turn_needs_tool_loop(
        content, settings=settings, user=user, **flags
    ) and turn_needs_tool_loop(content, settings=settings, user=user, web_search=True, **flags)
