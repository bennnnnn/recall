"""Follow-up questions for a subject answer.

One structured call on ``memory-model`` reads the student's question and the
reply. Chitchat makes no call. The strings are cached in Redis under the
assistant message id so reopening the chat does not call the model again.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.gateways.litellm_gateway import complete_structured
from app.services.chat.stream_events import build_related_prompts_event
from app.services.subject_solving import detect_subject
from app.services.text_normalize import collapse_ws

logger = logging.getLogger(__name__)

RELATED_PROMPTS_TIMEOUT_SECONDS = 6.0
RELATED_PROMPTS_TTL_SECONDS = 7 * 24 * 60 * 60
_ANSWER_CHARS = 800
_QUESTION_CHARS = 500
_MAX_QUESTIONS = 3
_KEY = "related_prompts:{message_id}"
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_CONTENT_WORD = re.compile(r"[a-z]{5,}")

# Biology is not a solver subject. These cues only decide whether to ask the
# model for follow-up questions. They are not a list of questions to show.
_BIOLOGY_CUES = (
    "dilution",
    "punnett",
    "hardy-weinberg",
    "hardy weinberg",
    "allele",
    "enzyme kinetics",
    "michaelis",
    "population growth",
    "photosynthesis",
    "mitosis",
)

_SYSTEM = (
    "You write the next three questions this student would ask about the "
    "problem they just worked. Each item is one full question about this "
    "same problem: why the result came out that way, a harder case of the "
    "same idea, or the neighboring idea. "
    "Keep a number or a word from that problem in every question. "
    "Write each equation or quantity in $...$, as in $x^2 = 9$. "
    'Return JSON {"questions": ["...", "...", "..."]}. '
    "Do not repeat the student's question. "
    "Do not keep the same sentence and only change a number. "
    "No heading and no label."
)


class RelatedQuestions(BaseModel):
    questions: list[str] = Field(min_length=1, max_length=_MAX_QUESTIONS)


def subject_for_related(text: str) -> str | None:
    """Math, physics, chemistry, or biology. Anything else is skipped."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return None
    detected = detect_subject(cleaned)
    if detected is not None:
        return detected
    lowered = cleaned.casefold()
    if any(cue in lowered for cue in _BIOLOGY_CUES):
        return "biology"
    return None


def _digit_skeleton(text: str) -> str:
    return _NUMBER.sub("#", collapse_ws(text).casefold())


def _folded_question(text: str) -> str:
    return collapse_ws(text).casefold().rstrip("?").strip()


def _keep_question(question: str, candidate: str) -> bool:
    cleaned = collapse_ws(candidate)
    if not cleaned:
        return False
    folded = cleaned.casefold()
    if _folded_question(cleaned) == _folded_question(question):
        return False
    if "suggestion" in folded:
        return False
    if _digit_skeleton(cleaned) == _digit_skeleton(question):
        return False
    # "3 + 4" has no long word. A follow-up that mentions neither 3 nor 4
    # left the problem. A physics follow-up can skip the digits when it
    # still says force or object. A numberless question may ask the
    # neighboring idea, so this check stays off there.
    anchors = _problem_anchors(question)
    if anchors and not _mentions_anchor(cleaned, anchors):
        return False
    return True


def _problem_anchors(question: str) -> set[str]:
    folded = collapse_ws(question).casefold()
    numbers = set(_NUMBER.findall(folded))
    if not numbers:
        return set()
    return numbers | set(_CONTENT_WORD.findall(folded))


def _mentions_anchor(follow_up: str, anchors: set[str]) -> bool:
    folded = collapse_ws(follow_up).casefold()
    return any(re.search(rf"\b{re.escape(anchor)}\b", folded) for anchor in anchors)


def _accepted_questions(question: str, raw: list[str]) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not _keep_question(question, item):
            continue
        cleaned = collapse_ws(item)
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append(cleaned)
        if len(kept) == _MAX_QUESTIONS:
            break
    return kept


def _answer_excerpt(answer: str) -> str:
    text = re.sub(r"```[a-z0-9_-]*", " ", answer, flags=re.IGNORECASE)
    text = text.replace("```", " ")
    return collapse_ws(text)[:_ANSWER_CHARS]


async def generate_related_questions(
    settings: Settings,
    question: str,
    answer: str,
) -> list[str]:
    """Three follow-up questions, or none when this line is not a subject."""
    if subject_for_related(question) is None:
        return []
    excerpt = _answer_excerpt(answer)
    if not excerpt:
        return []
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": (
                f"Student question:\n{collapse_ws(question)[:_QUESTION_CHARS]}\n\nReply:\n{excerpt}"
            ),
        },
    ]
    try:
        parsed = await asyncio.wait_for(
            complete_structured(
                settings=settings,
                model_alias="memory-model",
                messages=messages,
                schema=RelatedQuestions,
                max_tokens=256,
                timeout_seconds=RELATED_PROMPTS_TIMEOUT_SECONDS,
                allow_fallback=False,
            ),
            timeout=RELATED_PROMPTS_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning("Related questions timed out")
        return []
    except Exception:
        logger.warning("Related questions failed", exc_info=True)
        return []
    if parsed is None:
        return []
    return _accepted_questions(question, parsed.questions)


def _cache_key(message_id: str) -> str:
    return _KEY.format(message_id=message_id)


async def store_related_prompts(redis: Redis, message_id: str, prompts: list[str]) -> None:
    await redis.set(
        _cache_key(message_id),
        json.dumps(prompts),
        ex=RELATED_PROMPTS_TTL_SECONDS,
    )


async def load_related_prompts(redis: Redis, message_id: str) -> list[str]:
    """Cached questions for one assistant message. A miss does not call the model."""
    try:
        raw = await redis.get(_cache_key(message_id))
    except Exception:
        logger.warning("Related questions cache read failed", exc_info=True)
        return []
    if not isinstance(raw, str) or not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    prompts = [item.strip() for item in data if isinstance(item, str) and item.strip()]
    return prompts[:_MAX_QUESTIONS]


async def _related_prompts_event(
    redis: Redis,
    settings: Settings,
    *,
    message_id: str,
    question: str,
    answer: str,
) -> dict[str, Any] | None:
    prompts = await generate_related_questions(settings, question, answer)
    if not prompts:
        return None
    try:
        await store_related_prompts(redis, message_id, prompts)
    except Exception:
        logger.warning("Related questions cache write failed", exc_info=True)
    return build_related_prompts_event(message_id, prompts)


def schedule_related_prompts(
    result: dict[str, Any] | None,
    redis: Redis,
    settings: Settings,
    *,
    message_id: str,
    question: str,
    answer: str,
) -> None:
    """Start the model call without waiting. The transport sends the event after done."""
    if result is not None and result.get("completion") not in (None, "complete"):
        return
    if subject_for_related(question) is None or not collapse_ws(answer):
        return
    task = create_background_task(
        _related_prompts_event(
            redis,
            settings,
            message_id=message_id,
            question=question,
            answer=answer,
        ),
        name="related_prompts",
    )
    if result is not None:
        result["_related_task"] = task
