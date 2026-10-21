"""What a streamed reply shows before its answer: reasoning on its own channel.

LiteLLM puts a provider's reasoning in ``delta.reasoning_content`` (OpenRouter's
``reasoning``). Its text is never forwarded (the chat UI must not show CoT); that
it arrives is what the stream reads.
"""

from __future__ import annotations

from typing import Any


def reasoning_delta(delta: Any) -> bool:
    """True when this chunk carries reasoning text on the provider's own channel."""
    text = getattr(delta, "reasoning_content", None) if delta is not None else None
    return isinstance(text, str) and bool(text.strip())
