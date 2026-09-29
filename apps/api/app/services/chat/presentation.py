"""Assistant Markdown presentation: boundaries, then calculation rows.

Server persist, direct replies, and the mobile preprocessor share this
contract. The mobile copy lives in ``lib/markdown/presentation.ts``.
"""

from __future__ import annotations

from app.services.chat.calculation_layout import layout_calculations
from app.services.chat.inline_boundaries import repair_inline_token_boundaries


def present_assistant_markdown(text: str) -> str:
    """Repair closed inline tokens, then split multi-step calculations."""
    if not text:
        return text
    return layout_calculations(repair_inline_token_boundaries(text))
