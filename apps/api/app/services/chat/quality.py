"""Post-generation quality detection (detect-only, no re-stream).

R-API-001 v1: after the assistant reply is finalized, compute a cheap
quality metric and log it as a structured warning. This gives visibility
into quality issues (refusals, suspiciously short answers, weak-model
mispicks) without breaking the streaming contract — tokens already went
to the client, so we never re-stream or modify the response.

Future versions can feed this metric back into routing decisions, prompt
adjustments, or a next-turn nudge. For now: log only.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.services.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

# Patterns that indicate a refusal / canned deflection. Matched on the
# stripped assistant text (case-insensitive). Kept tight to avoid
# false positives on legitimate "I can't do X because Y" explanations.
_REFUSAL_PATTERNS = (
    re.compile(r"^(?:i (?:can'?t|cannot|am unable to|apologize))\b", re.IGNORECASE),
    re.compile(r"^as an (?:ai|language model)\b", re.IGNORECASE),
    re.compile(r"^i'?m just an? ai\b", re.IGNORECASE),
    re.compile(r"^sorry, (?:but )?i (?:can'?t|cannot)\b", re.IGNORECASE),
)

# Below this many characters, a non-lightweight / non-quiz rich-context turn
# is suspiciously short. Tuned to avoid flagging brief-but-complete answers
# to simple questions ("Yes.", "No, that's not correct.") while catching
# one-word / empty-ish replies to rich turns.
_MIN_RICH_REPLY_CHARS = 40


@dataclass
class QualitySignal:
    """A single detected quality issue."""

    code: str
    detail: str


@dataclass
class QualityReport:
    """Result of post-generation quality detection."""

    signals: list[QualitySignal] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.signals)


def detect_quality_issues(ctx: StreamContext, assistant_text: str) -> QualityReport:
    """Compute a quality metric for the finalized assistant reply.

    Pure function (no IO) — safe to call in the background finalize path.
    Logs a structured warning when issues are found.
    """
    report = QualityReport()
    text = assistant_text.strip()

    # 1. Refusal / canned deflection.
    if text:
        for pattern in _REFUSAL_PATTERNS:
            if pattern.match(text):
                report.signals.append(
                    QualitySignal(
                        code="refusal_pattern",
                        detail=f"reply starts with a refusal pattern: {pattern.pattern}",
                    )
                )
                break

    # 2. Suspiciously short for a rich-context turn.
    # Skip: lightweight turns (greetings/acks), quiz/vocab answer turns
    # (brief feedback is expected), instant replies (canned), and image
    # gen turns (the "[Image: …]" row is always short).
    is_quiz_turn = ctx.skip_memory_jobs
    if (
        text
        and ctx.rich_context_turn
        and not ctx.lightweight_turn
        and not is_quiz_turn
        and not ctx.instant_reply
        and not ctx.terminal_image_content
        and len(text) < _MIN_RICH_REPLY_CHARS
    ):
        report.signals.append(
            QualitySignal(
                code="short_rich_reply",
                detail=f"rich-context reply is {len(text)} chars (threshold {_MIN_RICH_REPLY_CHARS})",
            )
        )

    if report.has_issues:
        codes = ",".join(s.code for s in report.signals)
        logger.warning(
            "turn_quality_issue user_id=%s chat_id=%s model=%s codes=%s "
            "reply_len=%d lightweight=%s rich_context=%s instant=%s",
            ctx.user_id,
            ctx.chat_id,
            ctx.model,
            codes,
            len(text),
            ctx.lightweight_turn,
            ctx.rich_context_turn,
            bool(ctx.instant_reply),
        )

    return report
