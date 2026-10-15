"""Follow-up questions under an answer, about what the user just asked.

One structured call on ``memory-model`` reads the question and the reply. A
subject problem gets a why, a what-if and a next step; any other real question
gets the next things a person would ask about the same topic. Small talk,
drafts, personal updates and short replies make no call. Every question is one
short line in the user's voice. The strings are cached in Redis under the
assistant message id so reopening the chat does not call the model again.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.core.background_tasks import create_background_task
from app.core.config import Settings
from app.gateways.litellm_gateway import complete_structured
from app.modules.chat.stream_events import build_related_prompts_event
from app.services.problem_followup import message_role_content
from app.services.subject_solving import detect_subject
from app.services.text_normalize import collapse_ws

logger = logging.getLogger(__name__)

RELATED_PROMPTS_TIMEOUT_SECONDS = 6.0
RELATED_PROMPTS_TTL_SECONDS = 7 * 24 * 60 * 60
_ANSWER_CHARS = 800
_QUESTION_CHARS = 500
_MAX_QUESTIONS = 3
_KEY = "related_prompts:{message_id}"
_FORGET_BATCH = 500
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_WORD = re.compile(r"[A-Za-z]{2,}")
_MATH_SPAN = re.compile(r"\$([^$\n]+)\$")
# A digit glued to a radical (`^5\sqrt{x}`) or to a variable (`x5`).
_GLUED_RADICAL = re.compile(r"\^\s*\d+\s*\\sqrt")
_GLUED_VARIABLE = re.compile(r"(?<![A-Za-z\\^_{])[A-Za-z]\d+")
_MIN_QUESTION_WORDS = 4
# One line on a phone, two at most: a follow-up is a tap, not a problem set.
_MAX_QUESTION_CHARS = 64
_MAX_QUESTION_WORDS = 12
# A general answer this short is a quick reply or a question back to the user.
_GENERAL_MIN_ANSWER_CHARS = 280
_GENERAL_MIN_QUESTION_WORDS = 3
# A follow-up ("why does that work?") belongs to the problem a few user lines
# back. Further than this is a stale thread, not the current one.
_THREAD_USER_TURNS = 3
_FOLLOW_UP_LEADS = frozenset(
    {
        "why",
        "how",
        "what",
        "when",
        "where",
        "which",
        "can",
        "could",
        "is",
        "are",
        "does",
        "do",
        "explain",
        "show",
        "give",
        "try",
        "solve",
        "find",
        "and",
        "but",
        "so",
        "if",
    }
)
_CONTENT_WORD = re.compile(r"[a-z]{5,}")
_UNIT_TOKEN = re.compile(r"[a-z]+/[a-z]+")

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

_SHAPE = (
    "Each one is a single short question in the user's own voice, as they would "
    "type it: 3 to 9 words, at most 60 characters, ending with ?. One sentence, no "
    "preamble, no number, no label, no quote marks. "
    "Do not ask what the reply already explained, and do not repeat the user's "
    "question or one they asked before. "
    'Return JSON {"questions": ["...", "...", "..."]}.'
)

_SYSTEM = (
    "You write the next three questions a student would tap to keep learning "
    "the problem they are working on, in this order: "
    "1. Understand: why a step or the result works. "
    "2. What if: the same problem with one number or condition changed, asked in "
    "a few words. "
    "3. Go further: the next idea this problem leads to. "
    "Name the quantity, never restate the whole problem: "
    '"Why convert km/h to m/s first?", "What if it took 10 s instead?", '
    '"How far does the car go in 5 s?". '
    "Write each equation in $...$ with spaces around =, as in $x^2 = 9$ or "
    "$\\sqrt{x} = 5$. A letter and a number stay separate: never $x5$, and "
    "never a number stuck to a radical like $^5\\sqrt{x}$. "
    f"{_SHAPE}"
)

_GENERAL_SYSTEM = (
    "You write up to three follow-up questions the user is likely to tap next, "
    "about exactly what they just asked. Each digs one step further into the same "
    "topic: a detail the reply only touched on, the usual next step, or a likely "
    '"what if". Stay on their topic and in the language they wrote in. '
    "Return an empty list when nothing would help: small talk, a personal update, "
    "a message or text they asked you to write, a reminder or a setting. "
    f"{_SHAPE}"
)


class RelatedQuestions(BaseModel):
    # Asked for three; a fourth or fifth is filtered, not a failed call.
    questions: list[str] = Field(default_factory=list, max_length=2 * _MAX_QUESTIONS)


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


def _continues_thread(text: str) -> bool:
    """A question or a "one more" about the open problem, not small talk."""
    from app.modules.chat.continuation_subject import is_new_problem_request, is_pure_continuation
    from app.modules.chat.prompt_constants.routing import is_lightweight_chat_turn

    cleaned = collapse_ws(text)
    if not cleaned or is_lightweight_chat_turn(cleaned):
        return False
    if is_pure_continuation(cleaned) or is_new_problem_request(cleaned):
        return True
    words = cleaned.casefold().split()
    return cleaned.endswith("?") or (bool(words) and words[0].strip(",.") in _FOLLOW_UP_LEADS)


def thread_problem(question: str, prior: Sequence[Any] | None) -> str | None:
    """The subject problem this line follows up on, or None.

    "Why do we divide distance by time?" names no subject itself, so the
    follow-ups would stop after the first tapped "why". It still belongs to
    the bike problem two lines back.
    """
    if subject_for_related(question) is not None:
        return question
    if not prior or not _continues_thread(question):
        return None
    users = 0
    for message in reversed(prior):
        role, content = message_role_content(message)
        if role != "user" or not content or not content.strip():
            continue
        users += 1
        if users > _THREAD_USER_TURNS:
            return None
        if subject_for_related(content) is not None:
            return content
    return None


def _digit_skeleton(text: str) -> str:
    return _NUMBER.sub("#", collapse_ws(text).casefold())


def _folded_question(text: str) -> str:
    return collapse_ws(text).casefold().rstrip("?").strip()


def _prev_significant(text: str) -> str:
    stripped = text.rstrip()
    return stripped[-1] if stripped else ""


def _space_math_span(span: str) -> str:
    """Put a space on each side of = and of a binary + or -."""
    out: list[str] = []
    i = 0
    n = len(span)
    while i < n:
        ch = span[i]
        if ch == "\\":
            j = i + 1
            while j < n and span[j].isalpha():
                j += 1
            out.append(span[i:j])
            i = j
            continue
        if ch in "^_":
            if i + 1 < n and span[i + 1] == "{":
                depth = 0
                j = i + 1
                while j < n:
                    if span[j] == "{":
                        depth += 1
                    elif span[j] == "}":
                        depth -= 1
                        if depth == 0:
                            j += 1
                            break
                    j += 1
                out.append(span[i:j])
                i = j
                continue
            out.append(ch)
            i += 1
            continue
        prev = _prev_significant("".join(out))
        binary = ch == "=" or (ch in "+-" and prev not in {"", "=", "+", "-", "*", "/", "(", "^"})
        if binary:
            if out and not "".join(out).endswith(" "):
                out.append(" ")
            out.append(f"{ch} ")
            i += 1
            while i < n and span[i] == " ":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out).strip()


def _symbols_stay_apart(text: str) -> bool:
    for span in _MATH_SPAN.findall(text):
        if _GLUED_RADICAL.search(span) or _GLUED_VARIABLE.search(span):
            return False
    return True


def _visible_text(text: str) -> str:
    """What the phone shows: ``$\frac{1}{2}$`` reads as about four characters."""

    def _inner(match: re.Match[str]) -> str:
        return re.sub(r"\\[A-Za-z]+|[{}]", "", match.group(1))

    return collapse_ws(_MATH_SPAN.sub(_inner, text))


def _one_short_line(text: str) -> bool:
    """One question that fits a line or two, not a restated problem."""
    visible = _visible_text(text)
    if len(visible) > _MAX_QUESTION_CHARS or len(visible.split()) > _MAX_QUESTION_WORDS:
        return False
    # "A car travels 120 km in 2 h. What is its speed?" is a problem set,
    # not a tap. A decimal point (2.5) is not a sentence end.
    return re.search(r"[.!?:;]\s+\S", visible.rstrip("?")) is None


def _prepare_question(candidate: str) -> str | None:
    """A short full question with a variable and a number kept apart, or none."""
    cleaned = collapse_ws(candidate).strip("\"'“”")
    letter_words = _WORD.findall(cleaned)
    # A sum such as "What is 3 + 5?" is short, and it still names the problem.
    # "How" does not.
    short_with_number = _NUMBER.search(cleaned) is not None and len(letter_words) >= 2
    long_enough = len(letter_words) >= _MIN_QUESTION_WORDS or short_with_number
    if not cleaned.endswith("?") or not long_enough:
        return None
    if not _one_short_line(cleaned) or not _symbols_stay_apart(cleaned):
        return None

    def _spaced(match: re.Match[str]) -> str:
        return f"${_space_math_span(match.group(1))}$"

    return _MATH_SPAN.sub(_spaced, cleaned)


# "What if it took 10 s?" and "Why does that work?" point back at the
# problem instead of naming it; a short follow-up is allowed to.
_BACK_REFERENCE = re.compile(
    r"^(?:what|and) if\b|\b(?:it|its|it's|this|that|these|those|they|same|instead)\b",
    re.IGNORECASE,
)
_STOP_WORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "also",
        "because",
        "been",
        "before",
        "being",
        "best",
        "better",
        "could",
        "does",
        "doing",
        "each",
        "from",
        "have",
        "here",
        "into",
        "just",
        "know",
        "like",
        "make",
        "more",
        "most",
        "much",
        "need",
        "only",
        "other",
        "should",
        "some",
        "than",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "thing",
        "things",
        "this",
        "what",
        "when",
        "where",
        "which",
        "while",
        "will",
        "with",
        "would",
        "your",
    }
)
_TOPIC_WORD = re.compile(r"[a-z]{4,}")


def _keep_question(
    question: str,
    candidate: str,
    problem: str | None,
    anchors: set[str],
) -> bool:
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
    if (
        problem is not None
        and problem != question
        and _folded_question(cleaned) == _folded_question(problem)
    ):
        return False
    # "3 + 4" has no long word. A follow-up that mentions neither 3 nor 4,
    # nor points back at the problem, left it.
    if anchors and not (_mentions_anchor(cleaned, anchors) or _BACK_REFERENCE.search(cleaned)):
        return False
    return True


def _problem_anchors(question: str) -> set[str]:
    folded = collapse_ws(question).casefold()
    numbers = set(_NUMBER.findall(folded))
    if not numbers:
        return set()
    # "Why convert km/h to m/s first?" names the problem by its unit.
    return numbers | set(_CONTENT_WORD.findall(folded)) | set(_UNIT_TOKEN.findall(folded))


def _topic_anchors(question: str, excerpt: str) -> set[str]:
    """Words that keep a general follow-up on the user's topic.

    The question's words, and the reply's longer words: "Can I use whole wheat
    flour?" stays with a sourdough answer that mentions flour. A question in a
    script without Latin letters has none, and the check stays off.
    """
    asked = {
        word
        for word in _TOPIC_WORD.findall(collapse_ws(question).casefold())
        if word not in _STOP_WORDS
    }
    if not asked:
        return set()
    replied = {
        word for word in _CONTENT_WORD.findall(excerpt.casefold()) if word not in _STOP_WORDS
    }
    return asked | replied


def _mentions_anchor(follow_up: str, anchors: set[str]) -> bool:
    folded = collapse_ws(follow_up).casefold()
    return any(re.search(rf"\b{re.escape(anchor)}\b", folded) for anchor in anchors)


def _accepted_questions(
    question: str,
    raw: list[str],
    problem: str | None = None,
    anchors: set[str] | None = None,
) -> list[str]:
    if anchors is None:
        anchors = _problem_anchors(question)
        if problem is not None and problem != question:
            anchors |= _problem_anchors(problem)
    kept: list[str] = []
    seen: set[str] = set()
    for item in raw:
        prepared = _prepare_question(item)
        if prepared is None or not _keep_question(question, prepared, problem, anchors):
            continue
        key = prepared.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append(prepared)
        if len(kept) == _MAX_QUESTIONS:
            break
    return kept


def _answer_excerpt(answer: str) -> str:
    text = re.sub(r"```[a-z0-9_-]*", " ", answer, flags=re.IGNORECASE)
    text = text.replace("```", " ")
    return collapse_ws(text)[:_ANSWER_CHARS]


# A line that asks for something to know: a question, or "explain", "tips for".
_ASKS_TO_KNOW = re.compile(
    r"^(?:how|what|what's|whats|why|when|where|which|who|whose|can|could|would|should|"
    r"is|are|was|were|do|does|did|will|explain|tell me|teach me|show me|give me|list|"
    r"compare|describe|summari[sz]e|recommend|suggest|help me|ideas?|tips?|best)\b",
    re.IGNORECASE,
)
# A reminder, a saved fact or a setting is done once it is done. "How do I
# remember vocabulary?" and "best to-do list app?" are questions, not commands.
_ADMIN_REQUEST = re.compile(
    r"\b(?:remind me|set (?:a |an )?(?:reminder|alarm|timer)|remember (?:that|this|my|me)\b|"
    r"don'?t forget|(?:add|put)\b.{0,40}\bto my (?:to-?do|list|schedule|reminders)|"
    r"my settings|my preferences|turn (?:on|off)|switch (?:on|off)|call me)",
    re.IGNORECASE,
)


def general_question(question: str, answer: str) -> bool:
    """A real question with a full answer, outside the subjects.

    Small talk, a personal update, a draft the user asked for, a reminder or a
    setting, and a short reply get no follow-ups. Small talk that reads like a
    question ("how's your day?") gets a short reply, which the length check
    catches.
    """
    from app.modules.chat.prompt_constants.routing import (
        is_lightweight_chat_turn,
        is_personal_disclosure_turn,
    )
    from app.modules.chat.prompt_constants.writing_kind import writing_request_kind

    cleaned = collapse_ws(question)
    if len(cleaned.split()) < _GENERAL_MIN_QUESTION_WORDS:
        return False
    if not (cleaned.endswith("?") or _ASKS_TO_KNOW.match(cleaned)):
        return False
    if is_lightweight_chat_turn(cleaned) or is_personal_disclosure_turn(cleaned):
        return False
    if writing_request_kind(cleaned) is not None or _ADMIN_REQUEST.search(cleaned):
        return False
    return len(_answer_excerpt(answer)) >= _GENERAL_MIN_ANSWER_CHARS


def _follow_up_topic(
    question: str,
    answer: str,
    prior: Sequence[Any] | None,
    *,
    allow_general: bool,
) -> tuple[str, str | None] | None:
    """("subject", problem) or ("general", None); None makes no call."""
    problem = thread_problem(question, prior)
    if problem is not None:
        return "subject", problem
    if allow_general and general_question(question, answer):
        return "general", None
    return None


async def generate_related_questions(
    settings: Settings,
    question: str,
    answer: str,
    prior: Sequence[Any] | None = None,
    *,
    allow_general: bool = True,
) -> list[str]:
    """Up to three short follow-up questions about what the user asked."""
    topic = _follow_up_topic(question, answer, prior, allow_general=allow_general)
    if topic is None:
        return []
    kind, problem = topic
    excerpt = _answer_excerpt(answer)
    if not excerpt:
        return []
    lines = []
    if kind == "subject":
        if problem is not None and problem != question:
            lines.append(f"Problem:\n{collapse_ws(problem)[:_QUESTION_CHARS]}")
        lines.append(f"Student question:\n{collapse_ws(question)[:_QUESTION_CHARS]}")
        system = _SYSTEM
        anchors = None
    else:
        lines.append(f"Question:\n{collapse_ws(question)[:_QUESTION_CHARS]}")
        system = _GENERAL_SYSTEM
        anchors = _topic_anchors(question, excerpt)
    lines.append(f"Reply:\n{excerpt}")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(lines)},
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
    return _accepted_questions(question, parsed.questions, problem, anchors)


def _cache_key(message_id: str) -> str:
    return _KEY.format(message_id=message_id)


async def store_related_prompts(redis: Redis, message_id: str, prompts: list[str]) -> None:
    await redis.set(
        _cache_key(message_id),
        json.dumps(prompts),
        ex=RELATED_PROMPTS_TTL_SECONDS,
    )


async def forget_related_prompts(redis: Redis, message_ids: Sequence[str]) -> int:
    """Drop cached questions for these replies. Returns how many keys went."""
    removed = 0
    keys = [_cache_key(message_id) for message_id in message_ids]
    for start in range(0, len(keys), _FORGET_BATCH):
        removed += int(await redis.unlink(*keys[start : start + _FORGET_BATCH]) or 0)
    return removed


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
    prior: Sequence[Any] | None = None,
    allow_general: bool = True,
) -> dict[str, Any] | None:
    prompts = await generate_related_questions(
        settings, question, answer, prior, allow_general=allow_general
    )
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
    prior: Sequence[Any] | None = None,
    allow_general: bool = True,
) -> None:
    """Start the model call without waiting. The transport sends the event after done.

    ``prior`` is the turn's recent window, which ties a "why?" to its problem.
    ``allow_general`` is off for a turn that was never a question (a greeting,
    an instant reply); subject follow-ups do not depend on it.
    """
    if result is not None and result.get("completion") not in (None, "complete"):
        return
    if not collapse_ws(answer):
        return
    if _follow_up_topic(question, answer, prior, allow_general=allow_general) is None:
        return
    task = create_background_task(
        _related_prompts_event(
            redis,
            settings,
            message_id=message_id,
            question=question,
            answer=answer,
            prior=prior,
            allow_general=allow_general,
        ),
        name="related_prompts",
    )
    if result is not None:
        result["_related_task"] = task
