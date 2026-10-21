"""What a streamed reply shows before its answer, and how long it may show nothing.

LiteLLM puts a provider's reasoning in ``delta.reasoning_content`` (OpenRouter's
``reasoning``). Its text is never forwarded (the chat UI must not show CoT); that
it arrives is what the stream reads: the model is thinking.

When another model can take over, an attempt that shows nothing for too long
is abandoned for it instead of waiting out the idle timeout (``first_reply_caps``).
Once the phone has something from the attempt (text, or the thinking it was
told about), no cap ends it: a fallback then would start the reply over.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.gateways.reasoning import thinking_value
from app.models import model_catalog
from app.models.model_catalog import ChatModel

# The catalog values that mean the model does not think.
_NO_THOUGHT = frozenset({"off", "none"})
# A cap shorter than this would end an attempt before its request is sent.
_MIN_CAP_SECONDS = 0.1


def reasoning_delta(delta: Any) -> bool:
    """True when this chunk carries reasoning text on the provider's own channel."""
    text = getattr(delta, "reasoning_content", None) if delta is not None else None
    return isinstance(text, str) and bool(text.strip())


def always_thinks(route: ChatModel) -> bool:
    """The model thinks even when asked not to (its "off" level is an effort)."""
    return route.thinking_off is not None and route.thinking_off not in _NO_THOUGHT


@dataclass(frozen=True)
class FirstReplyCaps:
    """How long one attempt may show nothing before the next model takes over."""

    # Nothing the phone can show yet: no visible text and no thinking.
    signal: float | None = None
    # No visible text yet, thinking or not: a reasoning model's silent-thought cap.
    text: float | None = None


def first_reply_caps(
    settings: Settings, alias: str, thinking: bool | str | None, *, has_next: bool
) -> FirstReplyCaps:
    """The caps for one attempt. The last model in the chain has none: waiting is
    all that is left, and a cap would only fail the turn sooner."""
    if not has_next:
        return FirstReplyCaps()
    route = model_catalog.get(alias)
    text = (
        settings.chat_stream_first_content_timeout_seconds
        if model_catalog.is_reasoning_alias(alias)
        else None
    )
    if always_thinks(route):
        # The free plan's hard and maths lane: its reasoning streams from the start.
        signal: float | None = settings.chat_stream_first_thought_timeout_seconds
    elif route.tier == "fast" and thinking_value(route, thinking) in _NO_THOUGHT:
        # Auto's everyday lane: no thinking, first text in about a second.
        signal = settings.chat_stream_first_text_timeout_seconds
    else:
        signal = None
    return FirstReplyCaps(signal=signal, text=text)


class FirstReplyWatch:
    """One attempt's first-reply caps, and what it has shown so far."""

    def __init__(self, caps: FirstReplyCaps) -> None:
        start = time.monotonic()
        # (seconds, deadline) for each cap the attempt has.
        self._signal = _cap(start, caps.signal)
        self._text = _cap(start, caps.text)
        self.shown_text = False
        self.shown_thinking = False

    def _live(self) -> list[tuple[str, float, float]]:
        live: list[tuple[str, float, float]] = []
        if self._signal is not None and not (self.shown_text or self.shown_thinking):
            live.append(("signal", *self._signal))
        if self._text is not None and not self.shown_text:
            live.append(("text", *self._text))
        return live

    def bound(self, limit: float) -> float:
        """``limit`` cut to the time left on the caps still running."""
        now = time.monotonic()
        for _name, _seconds, deadline in self._live():
            limit = min(limit, deadline - now)
        return max(0.0, limit)

    def expired(self) -> str | None:
        """The cap that ran out ("first signal 3.0s"), or None."""
        now = time.monotonic()
        for name, seconds, deadline in self._live():
            if now >= deadline:
                return f"first {name} {seconds}s"
        return None

    def saw(self, *, text: str, thinking: bool) -> bool:
        """Record one chunk: visible ``text`` ends both caps, ``thinking`` the signal cap.

        True the first time the model is seen thinking before any visible text,
        which is when the phone can be told it is thinking.
        """
        if text.strip():
            self.shown_text = True
        if not thinking or self.shown_text or self.shown_thinking:
            return False
        self.shown_thinking = True
        return True


@dataclass
class StreamAttempt:
    """One model's try at a reply, as the caller's health record reads it."""

    alias: str
    failed: bool = False
    # From the request to the provider's first reasoning or text; None if none came.
    first_delta_ms: int | None = None
    # From the request to the end of the try; None while it streams, or after a stop.
    elapsed_ms: int | None = None
    _started: float = field(default_factory=time.monotonic, init=False, repr=False)

    def _ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)

    def delta(self) -> None:
        """The provider sent reasoning or text."""
        if self.first_delta_ms is None:
            self.first_delta_ms = self._ms()

    def end(self, *, failed: bool) -> None:
        self.failed = failed
        self.elapsed_ms = self._ms()


def _cap(start: float, seconds: float | None) -> tuple[float, float] | None:
    if seconds is None:
        return None
    return seconds, start + max(_MIN_CAP_SECONDS, seconds)
