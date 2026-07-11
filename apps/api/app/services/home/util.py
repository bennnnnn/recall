"""Shared home-screen helpers (timezone, seed, overlap, text filters)."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Literal, NamedTuple, TypeVar
from zoneinfo import ZoneInfo

from app.models.orm import User
from app.models.schemas import HomeProjectHighlight, HomeStarter
from app.services import time_context as time_context_service

MAX_STARTERS = 5
MORNING_START_HOUR = 5
EMAIL_END_HOUR = 11
CALENDAR_TODAY_END_HOUR = 12
CALENDAR_TOMORROW_START_HOUR = 12
CALENDAR_TOMORROW_END_HOUR = 22
REFLECT_START_HOUR = 15
_HOME_MEMORY_TYPES = frozenset({"project", "focus", "preference"})
_INTERNAL_TEXT = re.compile(
    r"^(?:the\s+)?user(?:'s|\s+name\s+is|\s+email\s+is|\s+id\s+is)\b",
    re.IGNORECASE,
)
_USER_PREFIX = re.compile(
    r"^(?:the\s+)?user(?:'s|\s+is|\s+has|\s+wants\s+to|\s+is\s+trying\s+to|\s+is\s+working\s+on)\s+",
    re.IGNORECASE,
)
_LANGUAGE_LEARNING = re.compile(
    r"\b("
    r"learn(?:ing)?\s+english|english\s+(?:learner|learning|practice|vocabulary|vocab)|"
    r"studying\s+english|improve\s+(?:my\s+)?english|"
    r"learn(?:ing)?\s+(?:a\s+)?(?:new\s+)?language|language\s+learner|"
    r"vocabulary\s+practice|practice\s+(?:my\s+)?english|"
    r"vocabulary\s+learning|vocabular\w*"
    r")\b",
    re.IGNORECASE,
)

T = TypeVar("T")
CompletedDaily = tuple[str, Literal["language", "trivia"]]


class ProjectHomeContent(NamedTuple):
    starters: list[HomeStarter]
    subtitle: str | None
    highlight: HomeProjectHighlight | None
    completed_daily: list[CompletedDaily]


def resolve_home_tz(user: User, client_timezone: str | None = None) -> ZoneInfo:
    return time_context_service.resolve_timezone(
        time_context_service.effective_timezone(user.timezone, client_timezone)
    )


def local_hour_for_tz(tz: ZoneInfo) -> int:
    return datetime.now(tz).hour


def day_seed(user: User, tz: ZoneInfo) -> int:
    day = datetime.now(tz).strftime("%Y-%m-%d")
    digest = hashlib.sha256(f"{user.id}:{day}".encode()).hexdigest()
    return int(digest[:8], 16)


def rotate_list(items: list[T], seed: int) -> list[T]:
    if len(items) <= 1:
        return items
    rotated = list(items)
    for i in range(len(rotated) - 1, 0, -1):
        j = (seed + i * 7919) % (i + 1)
        rotated[i], rotated[j] = rotated[j], rotated[i]
    return rotated


def local_hour(user: User, tz: ZoneInfo | None = None) -> int:
    return local_hour_for_tz(tz or time_context_service.resolve_timezone(user.timezone))


def looks_internal(text: str) -> bool:
    clean = text.strip()
    if not clean:
        return True
    return bool(_INTERNAL_TEXT.match(clean))


def looks_like_language_learning(text: str) -> bool:
    return bool(_LANGUAGE_LEARNING.search(text.strip()))


def short_phrase(text: str, *, limit: int = 36) -> str:
    clean = text.strip().rstrip(".")
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1].rstrip()}…"


def normalize_overlap_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def overlap_tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", normalize_overlap_text(text)) if len(token) >= 3
    }


def texts_overlap(a: str, b: str) -> bool:
    left = normalize_overlap_text(a)
    right = normalize_overlap_text(b)
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    left_tokens = overlap_tokens(left)
    right_tokens = overlap_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    shared = left_tokens & right_tokens
    if len(shared) >= 2:
        return True
    shorter = min(len(left_tokens), len(right_tokens))
    return len(shared) >= 1 and len(shared) / shorter >= 0.5


def overlaps_any(text: str, anchors: list[str]) -> bool:
    return any(texts_overlap(text, anchor) for anchor in anchors)
