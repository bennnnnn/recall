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

import json
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

_JSON_FENCE_LANGS = frozenset({"graph", "geometry", "places", "sources"})
_ANSWER_LANGS = frozenset({"answer", "result", "final"})


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


@dataclass(frozen=True)
class _Fence:
    lang: str
    body: str
    closed: bool
    start: int
    end: int


def _fence_lang(info: str) -> str:
    stripped = info.strip()
    if not stripped:
        return ""
    space = stripped.find(" ")
    token = stripped if space < 0 else stripped[:space]
    return token.lower()


def _iter_fences(text: str) -> list[_Fence]:
    """Walk ``` fences with linear ``find`` (no nested regex)."""
    fences: list[_Fence] = []
    index = 0
    length = len(text)
    while True:
        start = text.find("```", index)
        if start < 0:
            break
        lang_start = start + 3
        newline = text.find("\n", lang_start)
        if newline < 0:
            fences.append(
                _Fence(
                    lang=_fence_lang(text[lang_start:]),
                    body="",
                    closed=False,
                    start=start,
                    end=length,
                )
            )
            break
        lang = _fence_lang(text[lang_start:newline])
        close = text.find("```", newline + 1)
        if close < 0:
            fences.append(
                _Fence(
                    lang=lang,
                    body=text[newline + 1 :],
                    closed=False,
                    start=start,
                    end=length,
                )
            )
            break
        fences.append(
            _Fence(
                lang=lang,
                body=text[newline + 1 : close],
                closed=True,
                start=start,
                end=close + 3,
            )
        )
        index = close + 3
    return fences


def _collect_format_signals(text: str) -> list[QualitySignal]:
    if not text:
        return []
    fences = _iter_fences(text)
    signals: list[QualitySignal] = []

    for fence in fences:
        if fence.lang not in _ANSWER_LANGS or not fence.closed:
            continue
        body = fence.body.strip()
        if not body:
            continue
        rest = f"{text[: fence.start]}{text[fence.end :]}"
        if body in rest:
            signals.append(
                QualitySignal(
                    code="duplicate_answer",
                    detail="```answer body also appears in nearby prose",
                )
            )
            break

    source_fences = [fence for fence in fences if fence.lang == "sources"]
    if len(source_fences) > 1 or (len(source_fences) == 1 and text[source_fences[0].end :].strip()):
        signals.append(
            QualitySignal(
                code="raw_sources_in_body",
                detail="```sources fence is not a single trailing canonical block",
            )
        )

    if any(not fence.closed for fence in fences):
        signals.append(
            QualitySignal(
                code="unclosed_rich_fence",
                detail="assistant text has an unclosed ``` fence",
            )
        )

    for fence in fences:
        if fence.lang not in _JSON_FENCE_LANGS or not fence.closed:
            continue
        body = fence.body.strip()
        if not body:
            continue
        try:
            json.loads(body)
        except json.JSONDecodeError:
            signals.append(
                QualitySignal(
                    code="malformed_json_fence",
                    detail=f"```{fence.lang} body is not valid JSON",
                )
            )
            break

    return signals


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

    report.signals.extend(_collect_format_signals(text))

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
