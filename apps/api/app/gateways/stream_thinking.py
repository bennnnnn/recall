"""How long, and how far, one streamed reply may think before its answer.

A turn's thinking level picks the model's reasoning effort (``reasoning``). An effort
does not bound the thinking: on a 20-part question DeepSeek, Qwen and GLM each thought
until the output cap ran out and wrote no answer, and the backup models did the same
(2026-11-18). So an attempt that thinks gets its own token budget on top of the reply's
(held exactly where the model takes a reasoning cap), and a ceiling on thinking without an
answer. Thinking that runs out of either is the request's fault, not the model's: the
reply goes on without thinking, on the next model or, when it was the last, once more on
the same one.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.gateways.reasoning import thinking_value
from app.gateways.stream_signals import NO_THOUGHT, THOUGHT_OUT, FirstReplyWatch
from app.models.model_catalog import ChatModel

logger = logging.getLogger(__name__)

# Reasoning text per token, to hold a model that takes no reasoning cap to the budget:
# DeepSeek streamed 2.6 characters a token, GLM 3.7 and Qwen 2.2 (probes, 2026-11-18). The
# high end, so a model is cut no sooner than its budget (DeepSeek near 6k tokens).
_REASONING_CHARS_PER_TOKEN = 4
# A wait cut to the ceiling may wake a hair before it: still the ceiling, not an idle stall.
_CEILING_SLACK_SECONDS = 0.05

__all__ = ["THOUGHT_OUT", "AttemptThinking", "StreamClock", "ThinkingPlan", "as_attempt", "thinks"]


def thinks(route: ChatModel, thinking: bool | str | None) -> bool:
    """The request asks this model for a reasoning effort (not none, not off)."""
    value = thinking_value(route, thinking)
    return value is not None and value not in NO_THOUGHT


@dataclass(frozen=True)
class AttemptThinking:
    """What one attempt sends and how long it may think."""

    # The thinking level sent (``reasoning.ThinkingLevel``, a bool, or None).
    level: bool | str | None
    # Tokens for its thinking, on top of the reply's cap; 0 when it does not think.
    budget: int = 0
    # Seconds from its request to its first answer text; None when it is not held to it.
    answer_within: float | None = None
    # Held to its budget by its streamed reasoning (and the ceiling): only an attempt that
    # can give way, to another model or to the same one without thinking.
    held: bool = False
    # Silence while it thinks that gives way to the next model; None for the last one.
    stall_within: float | None = None

    def answer_by(self) -> float | None:
        """The monotonic deadline for its first answer text, counted from now."""
        return None if self.answer_within is None else time.monotonic() + self.answer_within

    @property
    def reasoning_chars(self) -> int | None:
        """The reasoning text its budget allows before an answer; None without one. A
        model that takes no cap (DeepSeek, GLM) thought one question past 24,000 tokens."""
        return self.budget * _REASONING_CHARS_PER_TOKEN if self.held else None


def as_attempt(thinking: AttemptThinking | bool | str | None) -> AttemptThinking:
    """A bare level as an attempt with no thinking budget or ceiling."""
    return thinking if isinstance(thinking, AttemptThinking) else AttemptThinking(thinking)


class ThinkingPlan:
    """One reply's thinking: the turn's level until thinking runs out on an attempt,
    then none for the attempts after it."""

    def __init__(self, settings: Settings, level: bool | str | None) -> None:
        self._settings = settings
        self.level = level

    def attempt(self, route: ChatModel, *, has_next: bool) -> AttemptThinking:
        """A model that thinks gets the budget's tokens on top of the reply's. It is held to
        the budget and the ceiling when it can give way: another model follows, or it can
        think less. GLM thinks at every level: as the last model at its lowest, holding it
        would only end the turn sooner (it ran to the reply's cap before)."""
        if not thinks(route, self.level):
            return AttemptThinking(self.level)
        held = has_next or self._thinks_less(route)
        return AttemptThinking(
            self.level,
            budget=max(0, self._settings.chat_reasoning_budget_tokens),
            answer_within=self._settings.chat_stream_thought_ceiling_seconds if held else None,
            held=held,
            stall_within=self._settings.chat_stream_thought_idle_seconds if has_next else None,
        )

    def _thinks_less(self, route: ChatModel) -> bool:
        """Without thinking, this model sends a different reasoning level."""
        return thinking_value(route, False) != thinking_value(route, self.level)

    def drop(self, aliases: list[str], route: ChatModel, *, last: bool) -> bool:
        """Thinking ran out on ``route``: the attempts after it go without, and the last
        model is tried once more without (appended to ``aliases``) when that sends less
        thinking. False when the reply had already stopped thinking."""
        if self.level is None or self.level is False or self.level == "off":
            return False
        again = last and self._thinks_less(route)
        self.level = False
        logger.warning(
            "Chat stream %s thought without answering; going on without thinking", route.id
        )
        if again:
            aliases.append(route.id)
        return True


class StreamClock:
    """One attempt's clocks once its stream is open: the wall-clock cap on the whole reply,
    the idle wait per chunk, the first-reply cap (``FirstReplyWatch``), and the bounds on
    thinking with no answer yet: a deadline counted from the request (``answer_by``) and the
    attempt's reasoning budget (``AttemptThinking.reasoning_chars``)."""

    def __init__(
        self,
        settings: Settings,
        watch: FirstReplyWatch,
        answer_by: float | None,
        think: AttemptThinking,
    ) -> None:
        self.idle = settings.chat_stream_timeout_seconds
        self._max = max(1, settings.chat_stream_max_seconds)
        self._deadline = time.monotonic() + self._max
        self._watch = watch
        self._answer_by = answer_by
        self._reasoning_left = think.reasoning_chars
        self._stall = think.stall_within
        self.reasoning_chars = 0

    def reasoned(self, chars: int) -> None:
        """Reasoning text the attempt streamed."""
        self.reasoning_chars += chars
        if self._reasoning_left is not None:
            self._reasoning_left -= chars

    def meter_cut(self, usage: dict[str, int] | None) -> None:
        """An attempt cut off before the provider reported its usage: its reasoning, as
        tokens, is what the provider billed for its output (``llm_spend``)."""
        if usage is not None and "output" not in usage and self.reasoning_chars:
            usage["output"] = -(-self.reasoning_chars // _REASONING_CHARS_PER_TOKEN)

    def _answer_left(self) -> float | None:
        if self._answer_by is None or self._watch.shown_text:
            return None
        return self._answer_by - time.monotonic()

    def stop_reason(self) -> tuple[str, str] | None:
        """(what ran out, the failure's cause), or None while the stream may go on."""
        if time.monotonic() >= self._deadline:
            return f"wall-clock {self._max}s", "timeout"
        left = self._answer_left()
        if left is not None and left <= _CEILING_SLACK_SECONDS:
            return "thinking with no answer", THOUGHT_OUT
        if self._reasoning_left is not None and self._reasoning_left < 0:
            if not self._watch.shown_text:
                return "thinking past its budget", THOUGHT_OUT
        cap = self._watch.expired()
        return (cap, "cap") if cap is not None else None

    def _idle(self) -> float:
        """The silence allowed before the next chunk: shorter while it thinks unanswered
        and another model can take over (``chat_stream_thought_idle_seconds``)."""
        if self._stall is not None and not self._watch.shown_text:
            return min(self.idle, self._stall)
        return self.idle

    def next_wait(self) -> float:
        """How long the next chunk may take."""
        limit = min(self._idle(), self._deadline - time.monotonic())
        left = self._answer_left()
        if left is not None:
            limit = min(limit, left)
        return self._watch.bound(limit)

    def idle_reason(self) -> tuple[str, str]:
        """What ran out when a chunk did not come in time and nothing else had."""
        return f"idle {self._idle():g}s", "timeout"
